#!/usr/bin/env python3
"""Compile translated GalTransl JSONs (`work/gt_output/`) into `yureaka_en.dat` overlay table.

Architecture (Zero-Crash, Zero-SCRIPT.SRC-Edit):
- `SCRIPT.SRC` (`Sv20`) references `TEXT.DAT` by *original absolute byte offset* (`0x10..0x1d5b10`).
- Modifying `TEXT.DAT` directly shifts byte offsets and crashes the engine unless every `SCRIPT.SRC`
  text push is relocated without colliding with voice/sprite IDs.
- Instead, this compiler outputs a compact binary overlay table (`yureaka_en.dat`, magic `YUR1`)
  mapping `original_abs_offset -> (u32 text_id, word-wrapped CP932 string)`.
- `version.dll` hooks `yureaka.exe!0x004589f0` (the single TEXT.DAT reader in the engine) and
  serves translated strings directly by original offset, leaving `data.pac` / `SCRIPT.SRC` 100%
  untouched, removing string length limits (up to 4,090 bytes), and preserving save compatibility!
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import struct
import sys
from typing import Any

from PIL import ImageFont

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from text_extract import strip_ruby  # noqa: E402

OVERLAY_MAGIC = b"YUR1"
OVERLAY_VERSION = 1

TAG_TOKEN_RE = re.compile(r"(<[^<>]+>)")
PROTECTED_TAG_RE = re.compile(r"</?(?:d\d{4}|d|s\d+|s|center|c(?:#[^<>]+)?)>")

UNICODE_NORMALIZE_MAP = str.maketrans({
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": "\u201c",  # keep CP932 “ (0x8167) so Softpal favoice.dat CSV never breaks on ASCII 0x22!
    "\u201d": "\u201d",  # keep CP932 ” (0x8168)
    "\u2014": "--",
    "\u2015": "--",
    "\u2013": "-",
    "\u2212": "-",
    "\u2026": "...",
    "\u00a0": " ",
    "\u200b": "",
    "\ufeff": "",
    "\u3000": " ",
    "\u00ab": "\u201c",  # «
    "\u00bb": "\u201d",  # »
    "\u226a": "\u201c",  # ≪
    "\u226b": "\u201d",  # ≫
    "\u300c": "\u201c",  # 「
    "\u300d": "\u201d",  # 」
    "\u300e": "'",   # 『
    "\u300f": "'",   # 』
    "\uff08": "(",   # （
    "\uff09": ")",   # ）
    "\uff01": "!",   # ！
    "\uff1f": "?",   # ？
    "\uff5e": "~",   # ～
    "\uff1a": ":",   # ：
    "\uff1b": ";",   # ；
    "\uff0c": ",",   # ，
    "\u3001": ", ",  # 、
    "\u3002": ".",   # 。
    "\u30fc": "-",   # ー (prolonged sound mark inside English shouting)
    "\u00e9": "e",
    "\u00e8": "e",
    "\u00ea": "e",
    "\u00e0": "a",
    "\u00e1": "a",
    "\u00ef": "i",
    "\u00f4": "o",
    "\u00fc": "u",
    "\u00c9": "E",
    "\u266a": "~",
})


def is_mostly_ascii(text: str) -> bool:
    """Detect English or punctuation-only lines (even with fullwidth JP punctuation or ー)."""
    stripped = TAG_TOKEN_RE.sub("", text).strip()
    if not stripped:
        return False
    jp_letters = sum(1 for c in stripped if ("\u3040" <= c <= "\u30ff" and c != "\u30fc") or "\u4e00" <= c <= "\u9fff")
    latin_letters = sum(1 for c in stripped if ("A" <= c <= "Z") or ("a" <= c <= "z"))
    if jp_letters == 0:
        return True
    return latin_letters > jp_letters * 2


def normalize_english_text(text: str, *, allow_cp932_symbols: bool = False) -> str:
    text = strip_ruby(text)
    if allow_cp932_symbols:
        tbl = dict(UNICODE_NORMALIZE_MAP)
        tbl.pop(ord("\u266a"), None)
        text = text.translate(tbl)
    else:
        text = text.translate(UNICODE_NORMALIZE_MAP)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Convert any remaining straight ASCII double quotes to CP932 curly quotes (“/”)
    # so Softpal's save/favoice.dat CSV never gets corrupted by nested ASCII 0x22 quotes!
    if '"' in text:
        out_chars: list[str] = []
        open_q = True
        for ch in text:
            if ch == '"':
                out_chars.append("\u201c" if open_q else "\u201d")
                open_q = not open_q
            else:
                out_chars.append(ch)
        text = "".join(out_chars)
    # Fix spacing artifacts around normalized punctuation (e.g. `"I'm here! "` or `,  `)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r' "\s+', ' "', text)
    text = re.sub(r'\s+"([.,!?])', r'"\1', text)
    return text.strip()


class PixelWordWrapper:
    """Measures text with Windows GDI GetGlyphOutlineA matching Pal.dll + version.dll hook
    to 0-pixel precision (with automatic Pillow FreeType fallback on non-Windows).
    """

    def __init__(
        self,
        font_path: pathlib.Path | None,
        font_size: int = 28,
        max_width_px: int = 795,
        max_lines: int = 3,
        *,
        height_scale_percent: int = 104,
        char_spacing_delta: int = -2,
        space_width_percent: int = 26,
        face_name: str = "Barlow Semi Condensed Medium",
    ):
        self.font_size = font_size
        self.create_font_height = (font_size * height_scale_percent + 50) // 100
        self.char_spacing_delta = char_spacing_delta
        self.space_width = max(4, (self.create_font_height * space_width_percent + 50) // 100)
        self.max_width_px = max_width_px
        self.max_lines = max_lines
        self.font_path = font_path
        self._gdi_widths: dict[str, int] | None = self._init_gdi_widths(font_path, face_name, self.create_font_height)
        self._font = None if self._gdi_widths is not None else self._load_font(font_path, font_size)

    def _init_gdi_widths(self, font_path: pathlib.Path | None, face_name: str, create_h: int) -> dict[str, int] | None:
        if sys.platform != "win32":
            return None
        try:
            import ctypes
            gdi32 = ctypes.windll.gdi32
            if font_path and font_path.exists():
                gdi32.AddFontResourceExA(str(font_path).encode("mbcs"), 0x10, 0)
            hdc = gdi32.CreateCompatibleDC(0)
            hf = gdi32.CreateFontA(create_h, 0, 0, 0, 400, 0, 0, 0, 1, 4, 0, 4, 0, face_name.encode("mbcs"))
            old = gdi32.SelectObject(hdc, hf)

            class FIXED(ctypes.Structure):
                _fields_ = [("fract", ctypes.c_ushort), ("value", ctypes.c_short)]
            class MAT2(ctypes.Structure):
                _fields_ = [("eM11", FIXED), ("eM12", FIXED), ("eM21", FIXED), ("eM22", FIXED)]
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            class GLYPHMETRICS(ctypes.Structure):
                _fields_ = [
                    ("gmBlackBoxX", ctypes.c_uint), ("gmBlackBoxY", ctypes.c_uint),
                    ("gmptGlyphOrigin", POINT), ("gmCellIncX", ctypes.c_short), ("gmCellIncY", ctypes.c_short),
                ]
            mat = MAT2(FIXED(0, 1), FIXED(0, 0), FIXED(0, 0), FIXED(0, 1))
            widths: dict[str, int] = {" ": self.space_width}
            for code in range(0x21, 0x7F):
                gm = GLYPHMETRICS()
                gdi32.GetGlyphOutlineA(hdc, code, 6, ctypes.byref(gm), 0, None, ctypes.byref(mat))
                # Matches Pal.dll (+3) + version.dll hook (char_spacing_delta)
                w = max(1, int(gm.gmCellIncX) + 3 + self.char_spacing_delta)
                widths[chr(code)] = w
            for ch, cp932_code in [("\u201c", 0x8167), ("\u201d", 0x8168)]:
                gm = GLYPHMETRICS()
                gdi32.GetGlyphOutlineA(hdc, cp932_code, 6, ctypes.byref(gm), 0, None, ctypes.byref(mat))
                widths[ch] = max(1, int(gm.gmCellIncX) + 3 + self.char_spacing_delta)
            gdi32.SelectObject(hdc, old)
            gdi32.DeleteObject(hf)
            gdi32.DeleteDC(hdc)
            return widths
        except Exception:
            return None

    @staticmethod
    def _load_font(font_path: pathlib.Path | None, size: int) -> ImageFont.FreeTypeFont:
        candidates = []
        if font_path is not None:
            candidates.append(font_path)
        candidates.extend([
            pathlib.Path(r"C:\Windows\Fonts\segoeui.ttf"),
            pathlib.Path(r"C:\Windows\Fonts\arial.ttf"),
        ])
        for p in candidates:
            if p.exists():
                return ImageFont.truetype(str(p), size=size)
        raise FileNotFoundError("No TrueType font found for pixel width measurement")

    def measure(self, text: str) -> float:
        plain = TAG_TOKEN_RE.sub("", text)
        if not plain:
            return 0.0
        if self._gdi_widths is not None:
            default_w = self.font_size
            return float(sum(self._gdi_widths.get(ch, default_w) for ch in plain))
        assert self._font is not None
        return float(self._font.getlength(plain))

    def wrap_paragraph(self, para: str) -> list[str]:
        if not para:
            return [""]
        raw_tokens = TAG_TOKEN_RE.split(para)
        words: list[str] = []
        cur = ""
        in_d_tag = False
        for tok in raw_tokens:
            if not tok:
                continue
            if tok.startswith("<") and tok.endswith(">"):
                if tok.startswith("<d") and len(tok) > 3:
                    in_d_tag = True
                elif tok == "</d>":
                    in_d_tag = False
                cur += tok
            elif in_d_tag:
                # Never insert a <br> line break inside <dNNNN>...</d> TIPS tags!
                cur += tok
            else:
                parts = tok.split(" ")
                cur += parts[0]
                for p in parts[1:]:
                    words.append(cur)
                    cur = p
        if cur or not words:
            words.append(cur)

        lines: list[str] = []
        cur_line = ""
        for w in words:
            candidate = w if not cur_line else f"{cur_line} {w}"
            if self.measure(candidate) <= self.max_width_px or not cur_line:
                cur_line = candidate
            else:
                lines.append(cur_line)
                cur_line = w
        if cur_line:
            lines.append(cur_line)
        return lines

    def wrap(self, text: str) -> tuple[str, int]:
        paras = re.split(r"\n|<br>", text)
        all_lines: list[str] = []
        for p in paras:
            all_lines.extend(self.wrap_paragraph(p.strip()))
        return "<br>".join(all_lines), len(all_lines)


def extract_protected_tags(text: str) -> list[str]:
    return PROTECTED_TAG_RE.findall(text)


def compute_original_offsets(orig_dec: bytes) -> dict[int, int]:
    """Return mapping `text_id -> original_abs_byte_offset` in pristine `TEXT.DAT.dec`."""
    pos = 16
    tid_to_off: dict[int, int] = {}
    while pos + 4 <= len(orig_dec):
        idx = struct.unpack_from("<I", orig_dec, pos)[0]
        tid_to_off[idx] = pos
        end = orig_dec.index(b"\x00", pos + 4)
        pos = end + 1
    return tid_to_off


def build_overlay_blob(items: list[tuple[int, int, bytes]]) -> bytes:
    """Build `YUR1` binary overlay sorted by `orig_abs_off` for O(log N) binary search."""
    items_sorted = sorted(items, key=lambda x: x[0])
    count = len(items_sorted)
    pool_offset = 16 + count * 16
    pool_parts: list[bytes] = []
    table_parts: list[bytes] = []
    cur_pool_off = 0
    for orig_abs_off, text_id, cp932_bytes in items_sorted:
        if b"\x00" in cp932_bytes:
            raise ValueError(f"NUL byte inside encoded string for text_id={text_id}")
        table_parts.append(struct.pack("<IIII", orig_abs_off, text_id, cur_pool_off, len(cp932_bytes)))
        pool_parts.append(cp932_bytes)
        pool_parts.append(b"\x00")
        cur_pool_off += len(cp932_bytes) + 1
    header = struct.pack("<4sIII", OVERLAY_MAGIC, OVERLAY_VERSION, count, pool_offset)
    return header + b"".join(table_parts) + b"".join(pool_parts)


def parse_overlay_blob(blob: bytes) -> list[tuple[int, int, str]]:
    """Parse and verify a `YUR1` overlay blob."""
    magic, ver, count, pool_off = struct.unpack_from("<4sIII", blob, 0)
    if magic != OVERLAY_MAGIC or ver != OVERLAY_VERSION:
        raise ValueError("Invalid YUR1 overlay header")
    out: list[tuple[int, int, str]] = []
    prev_off = -1
    for i in range(count):
        orig_off, tid, soff, slen = struct.unpack_from("<IIII", blob, 16 + i * 16)
        if orig_off <= prev_off:
            raise ValueError("YUR1 overlay entries not strictly sorted by orig_abs_off")
        prev_off = orig_off
        raw = blob[pool_off + soff : pool_off + soff + slen]
        if blob[pool_off + soff + slen] != 0:
            raise ValueError(f"Missing NUL terminator for tid={tid}")
        out.append((orig_off, tid, raw.decode("cp932", errors="strict")))
    return out


def inject_workspace(
    workspace_dir: pathlib.Path,
    *,
    font_path: pathlib.Path | None = None,
    font_size: int = 24,
    max_width_px: int = 810,
    max_lines: int = 3,
    output_dir: pathlib.Path | None = None,
    allow_partial: bool = True,
    strict_tags: bool = True,
    wrap_english: bool = True,
) -> dict[str, Any]:
    work_dir = workspace_dir / "work"
    orig_dir = work_dir / "original"
    gt_out_dir = work_dir / "gt_output"
    meta_dir = work_dir / "metadata"
    dist_dir = output_dir or (workspace_dir / "dist")
    dist_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((meta_dir / "manifest.json").read_text(encoding="utf-8"))
    orig_dec = (orig_dir / "TEXT.DAT.dec").read_bytes()
    if hashlib.sha256(orig_dec).hexdigest() != manifest["hashes"]["TEXT.DAT.dec"]:
        raise ValueError("work/original/TEXT.DAT.dec hash mismatch against manifest!")

    tid_to_off = compute_original_offsets(orig_dec)
    wrapper = PixelWordWrapper(font_path, font_size=font_size, max_width_px=max_width_px, max_lines=max_lines)

    # Load canonical speaker name fallback map from glossary/terms.json (catches any untranslated JP speaker slots)
    terms_path = work_dir / "glossary" / "terms.json"
    speaker_fallback: dict[str, str] = {}
    if terms_path.exists():
        speaker_fallback = json.loads(terms_path.read_text(encoding="utf-8")).get("speaker_names", {})

    overlay_map: dict[int, tuple[int, bytes]] = {}  # orig_abs_off -> (tid, cp932_bytes)
    stats: dict[str, Any] = {
        "files_total": len(manifest["files"]),
        "files_translated": 0,
        "files_missing_kept_original": 0,
        "records_updated": 0,
        "names_updated": 0,
        "overflow_warnings": [],
        "tag_errors": [],
        "encoding_errors": [],
    }

    for fmeta in manifest["files"]:
        fname = fmeta["file"]
        kind = fmeta["kind"]
        if kind == "tips_csv":
            continue

        out_json = gt_out_dir / fname
        if not out_json.exists():
            if not allow_partial:
                raise FileNotFoundError(f"Missing translated file: {out_json}")
            stats["files_missing_kept_original"] += 1
            continue

        rows = json.loads(out_json.read_text(encoding="utf-8"))
        if not isinstance(rows, list) or len(rows) != fmeta["count"]:
            raise ValueError(f"{fname}: expected {fmeta['count']} records, got {len(rows) if isinstance(rows, list) else type(rows)}")

        stats["files_translated"] += 1
        for r_idx, (rec, mrow) in enumerate(zip(rows, fmeta["rows"])):
            tid = mrow["text_id"]
            nid = mrow["name_id"]

            new_msg = rec.get("message")
            if not isinstance(new_msg, str):
                raise ValueError(f"{fname}[{r_idx}]: missing string 'message'")

            orig_tags = extract_protected_tags(mrow["raw_text"])
            new_tags = extract_protected_tags(new_msg)
            if orig_tags != new_tags:
                stats["tag_errors"].append({
                    "file": fname, "row": r_idx, "text_id": tid,
                    "expected_tags": orig_tags, "actual_tags": new_tags, "message": new_msg[:120],
                })

            if is_mostly_ascii(new_msg):
                final_msg = normalize_english_text(new_msg)
                if wrap_english and kind == "story" and not mrow.get("preserve_br", False):
                    final_msg, n_lines = wrapper.wrap(final_msg)
                    if n_lines > max_lines:
                        stats["overflow_warnings"].append({
                            "file": fname, "row": r_idx, "text_id": tid, "lines": n_lines, "message": final_msg,
                        })
            else:
                final_msg = strip_ruby(new_msg)

            # Only emit overlay entry if text actually differs from pristine raw_text
            if final_msg != mrow["raw_text"]:
                try:
                    enc = final_msg.encode("cp932", errors="strict")
                except UnicodeEncodeError as exc:
                    stats["encoding_errors"].append({
                        "file": fname, "row": r_idx, "text_id": tid, "error": str(exc), "message": final_msg[:120],
                    })
                else:
                    overlay_map[tid_to_off[tid]] = (tid, enc)
                    stats["records_updated"] += 1

            if nid is not None:
                if "name" not in rec or not isinstance(rec["name"], str):
                    raise ValueError(f"{fname}[{r_idx}]: expected 'name' slot for name_id={nid}")
                raw_n = rec["name"]
                if raw_n in speaker_fallback:
                    new_name = speaker_fallback[raw_n]
                elif is_mostly_ascii(raw_n):
                    new_name = normalize_english_text(raw_n)
                else:
                    new_name = raw_n
                if new_name != mrow["raw_name"]:
                    try:
                        enc_n = new_name.encode("cp932", errors="strict")
                    except UnicodeEncodeError as exc:
                        stats["encoding_errors"].append({
                            "file": fname, "row": r_idx, "text_id": nid, "error": str(exc), "message": new_name,
                        })
                    else:
                        overlay_map[tid_to_off[nid]] = (nid, enc_n)
                        stats["names_updated"] += 1

    if strict_tags and stats["tag_errors"]:
        raise ValueError(f"Aborted due to {len(stats['tag_errors'])} tag mismatch error(s). First: {stats['tag_errors'][0]}")
    if stats["encoding_errors"]:
        raise ValueError(f"Aborted due to {len(stats['encoding_errors'])} CP932 encoding error(s). First: {stats['encoding_errors'][0]}")

    items = [(off, tid, raw) for off, (tid, raw) in overlay_map.items()]
    blob = build_overlay_blob(items)

    # Roundtrip-verify the overlay blob
    parsed = parse_overlay_blob(blob)
    if len(parsed) != len(items):
        raise AssertionError("Overlay roundtrip entry count mismatch!")

    out_overlay = dist_dir / "yureaka_en.dat"
    out_overlay.write_bytes(blob)

    report = {
        "ok": True,
        "output_overlay": {
            "path": str(out_overlay),
            "entries": len(items),
            "size": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
        },
        "stats": {
            **stats,
            "overflow_warning_count": len(stats["overflow_warnings"]),
            "overflow_warnings": stats["overflow_warnings"][:50],
        },
    }
    (work_dir / "reports" / "inject-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compile gt_output JSONs into yureaka_en.dat overlay")
    ap.add_argument("--workspace", type=pathlib.Path, default=pathlib.Path(r"d:\Documents\yureaka_en"))
    ap.add_argument("--font", type=pathlib.Path, default=None)
    ap.add_argument("--font-size", type=int, default=24)
    ap.add_argument("--max-width", type=int, default=810)
    ap.add_argument("--max-lines", type=int, default=3)
    ap.add_argument("--output-dir", type=pathlib.Path, default=None)
    ap.add_argument("--strict-complete", action="store_true")
    ap.add_argument("--no-strict-tags", action="store_true")
    ap.add_argument("--no-wrap", action="store_true")
    args = ap.parse_args(argv)
    rep = inject_workspace(
        args.workspace,
        font_path=args.font,
        font_size=args.font_size,
        max_width_px=args.max_width,
        max_lines=args.max_lines,
        output_dir=args.output_dir,
        allow_partial=not args.strict_complete,
        strict_tags=not args.no_strict_tags,
        wrap_english=not args.no_wrap,
    )
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
