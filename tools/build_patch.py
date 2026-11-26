#!/usr/bin/env python3
"""End-to-end patch builder for 紅月ゆれる恋あかり (Akatsuki Yureru Koi Akari) English patch.

Assembles into `<workspace>/dist/` (never modifies the original game directory):
  - `data.pac`     (repacked with word-wrapped translated TEXT.DAT)
  - `csv.pac`      (repacked with English-tuned SYSTEM.INI: wider textbox, GDI font type 2, size 24)
  - `version.dll`  (x86 proxy hook for Google Font loading, proportional CreateFontA, title)
  - `yureaka_en.ini`
  - `en_fonts/`    (bundled Google Fonts TTFs)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import sys
from typing import Any

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from softpal_pac import repack_pac2_with_overrides  # noqa: E402
from text_inject import inject_workspace, normalize_english_text  # noqa: E402


def patch_tips_csv(raw_bytes: bytes, gt_output_tips_json: pathlib.Path) -> bytes:
    """Replace column 0 (display title) of TIPS.CSV with English titles from 002_tips_csv.json,
    preserving column 1 (hiragana reading for kana tab sorting) and columns 2-3 (PGD names).
    """
    if not gt_output_tips_json.exists():
        return raw_bytes
    rows = json.loads(gt_output_tips_json.read_text(encoding="utf-8"))
    lines = raw_bytes.decode("cp932", errors="strict").splitlines(keepends=True)
    out_lines: list[str] = []
    tip_idx = 0
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("//"):
            out_lines.append(ln)
            continue
        eol = "\r\n" if ln.endswith("\r\n") else ("\n" if ln.endswith("\n") else "")
        cols = s.split(",")
        if len(cols) >= 4 and tip_idx < len(rows):
            en_title = normalize_english_text(rows[tip_idx]["message"])
            # Fullwidth ASCII letters (ＨＲ -> HR, ＳＵＭＩＴＡＮＩ -> SUMITANI) + no commas in CSV col 0
            en_title = "".join(chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c for c in en_title)
            en_title = en_title.replace(",", " -").replace('"', "'").strip()
            cols[0] = f'"{en_title}"'
            out_lines.append(",".join(cols) + eol)
            tip_idx += 1
        else:
            out_lines.append(ln)
    return "".join(out_lines).encode("cp932", errors="strict")


def patch_system_ini(
    raw_bytes: bytes,
    *,
    font_size: int = 28,
    text_x: int = 260,
    text_y: int = 576,
    text_width: int = 830,
    text_height: int = 136,
) -> bytes:
    """Tune SYSTEM.INI for crisp proportional English typography fitting both textbox and backlog."""
    text = raw_bytes.decode("cp932", errors="strict")
    replacements = {
        "DEF_FONT_TYPE": "2",
        "FONT_SIZE": str(font_size),
        "TEXT_DRAW_X": str(text_x),
        "TEXT_DRAW_Y": str(text_y),
        "TEXT_DRAW_WIDTH": str(text_width),
        "TEXT_DRAW_HEIGHT": str(text_height),
        "HISTORY_NAME_X": "94",
        "HISTORY_TEXT_X": "94",
        "HISTORY_BACK_X": "935",
        "TIPS_LIST_CUT": "24",
        "FAVOICE_TEXT_SIZE": "28",
        "SAMPLE_TEXT": '"<c#c5d3e8 #95afdb>Sample text display preview.</c>"',
    }
    out_lines: list[str] = []
    for ln in text.splitlines(keepends=True):
        m = re.match(r"^(\s*)([A-Z0-9_]+)(\s*=\s*)([^\r\n;]*)(.*)$", ln, flags=re.DOTALL)
        if m and m.group(2) in replacements:
            indent, key, eq, _old_val, tail = m.groups()
            eol = "\r\n" if ln.endswith("\r\n") else ("\n" if ln.endswith("\n") else "")
            out_lines.append(f"{indent}{key}{eq}{replacements[key]}{eol}")
        else:
            out_lines.append(ln)
    return "".join(out_lines).encode("cp932", errors="strict")


def build_patch(
    workspace: pathlib.Path,
    *,
    out_dir: pathlib.Path | None = None,
    font_file: str = "BarlowSemiCondensed-Medium.ttf",
    font_size: int = 28,
    text_x: int = 260,
    text_y: int = 576,
    text_width: int = 830,
    text_height: int = 136,
    wrap_margin: int = 35,
    max_lines: int = 3,
    strict_complete: bool = False,
) -> dict[str, Any]:
    dist = out_dir or (workspace / "dist")
    dist.mkdir(parents=True, exist_ok=True)
    font_path = workspace / "assets" / "fonts" / font_file
    if not font_path.exists():
        raise FileNotFoundError(f"Font not found: {font_path}")

    # 1. Build yureaka_en.dat runtime overlay with word-wrapped translated text (data.pac stays original!)
    inject_rep = inject_workspace(
        workspace,
        font_path=font_path,
        font_size=font_size,
        max_width_px=text_width - wrap_margin,
        max_lines=max_lines,
        output_dir=dist,
        allow_partial=not strict_complete,
        strict_tags=True,
        wrap_english=True,
    )
    # Remove any stale repacked data.pac from dist so original data.pac is never overwritten
    stale_data_pac = dist / "data.pac"
    if stale_data_pac.exists():
        stale_data_pac.unlink()

    # 2. Build csv.pac with English-tuned SYSTEM.INI + translated TIPS.CSV
    orig_dir = workspace / "work" / "original"
    patched_ini = patch_system_ini(
        (orig_dir / "SYSTEM.INI").read_bytes(),
        font_size=font_size,
        text_x=text_x,
        text_y=text_y,
        text_width=text_width,
        text_height=text_height,
    )
    csv_overrides: dict[str, bytes] = {"SYSTEM.INI": patched_ini}
    tips_json = workspace / "work" / "gt_output" / "002_tips_csv.json"
    if tips_json.exists() and (orig_dir / "TIPS.CSV").exists():
        csv_overrides["TIPS.CSV"] = patch_tips_csv((orig_dir / "TIPS.CSV").read_bytes(), tips_json)
    csv_info = repack_pac2_with_overrides(orig_dir / "csv.pac", csv_overrides, dist / "csv.pac")

    # 2b. Build patch.pac with localized TIPS & UI .PGD overrides (preserving original EV102BA.PGD)
    pgd_dir = workspace / "work" / "pgd_overrides"
    patch_pac_info = None
    if pgd_dir.exists():
        pgd_overrides = {p.name.upper(): p.read_bytes() for p in sorted(pgd_dir.glob("*.PGD"))}
        if pgd_overrides:
            patch_pac_info = repack_pac2_with_overrides(orig_dir / "patch.pac", pgd_overrides, dist / "patch.pac")

    # 3. Copy x86 hook DLL, INI, and bundled Google Fonts
    hook_dir = workspace / "hook"
    shutil.copy2(hook_dir / "version.dll", dist / "version.dll")
    shutil.copy2(hook_dir / "yureaka_en.ini", dist / "yureaka_en.ini")
    fonts_dst = dist / "en_fonts"
    fonts_dst.mkdir(parents=True, exist_ok=True)
    copied_fonts: list[str] = []
    for ttf in sorted((workspace / "assets" / "fonts").glob("*.ttf")):
        if "NotoSans" in ttf.name:
            continue
        shutil.copy2(ttf, fonts_dst / ttf.name)
        copied_fonts.append(ttf.name)

    report = {
        "ok": True,
        "dist_dir": str(dist),
        "font_used_for_wrapping": font_file,
        "font_size": font_size,
        "text_draw_width": text_width,
        "wrap_width_px": text_width - wrap_margin,
        "overlay": inject_rep["output_overlay"],
        "csv_pac": csv_info,
        "patch_pac": patch_pac_info,
        "bundled_fonts": copied_fonts,
        "inject_stats": inject_rep["stats"],
    }
    (workspace / "work" / "reports" / "build-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build 紅月ゆれる恋あかり English translation patch")
    ap.add_argument("--workspace", type=pathlib.Path, default=pathlib.Path(r"d:\Documents\yureaka_en"))
    ap.add_argument("--out-dir", type=pathlib.Path, default=None)
    ap.add_argument("--font", default="BarlowSemiCondensed-Medium.ttf")
    ap.add_argument("--font-size", type=int, default=28)
    ap.add_argument("--text-x", type=int, default=260)
    ap.add_argument("--text-y", type=int, default=576)
    ap.add_argument("--text-width", type=int, default=830)
    ap.add_argument("--text-height", type=int, default=136)
    ap.add_argument("--strict-complete", action="store_true")
    args = ap.parse_args(argv)
    rep = build_patch(
        args.workspace,
        out_dir=args.out_dir,
        font_file=args.font,
        font_size=args.font_size,
        text_x=args.text_x,
        text_y=args.text_y,
        text_width=args.text_width,
        text_height=args.text_height,
        strict_complete=args.strict_complete,
    )
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
