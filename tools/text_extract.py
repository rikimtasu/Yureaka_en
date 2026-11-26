#!/usr/bin/env python3
"""Extract Softpal TEXT.DAT & TIPS.CSV of 紅月ゆれる恋あかり into per-scene GalTransl JSONs.

Design:
- Keeps the original game directory strictly read-only.
- Saves pristine backups and SHA-256 hashes under `<workspace>/work/original/`.
- Separates translatable UI/BGM/story entries from engine-internal INI keys & debug logs.
- Pairs Softpal's trailing speaker entries (`[id] dialogue`, `[id+1] speaker`) into
  standard GalTransl JSON objects (`{"name": ..., "message": ...}`).
- Drops Japanese ruby tags (`<rREADING>BASE</r>` -> `BASE`) and joins Japanese soft-wrap
  `<br>` / `<br>\\u3000` inside story lines so LLM pipelines receive clean sentences, while
  preserving clickable TIPS links (`<dNNNN>...</d>`), `<sN>`, `<center>`, `<c#...>`.
- Saves complete 1:1 raw ID mapping in `work/metadata/manifest.json` and verifies
  byte-for-byte SHA-256 lossless roundtrip of `TEXT.DAT` and `data.pac`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import struct
import sys
from collections import Counter
from typing import Any

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from softpal_pac import (  # noqa: E402
    decrypt_softpal_table,
    encrypt_softpal_table,
    read_pac2_member,
    repack_pac2_with_overrides,
)

TEXT_DAT_HEADER = b"$TEXT_LIST__"

# Explicitly audited translatable system/UI IDs in 0..1030 (everything else in 0..1030
# and 48454..48455 is an INI key/section, printf format, debug log, or asset filename).
UI_TRANSLATABLE_IDS: dict[int, str] = {
    179: "tooltip_skip",
    180: "tooltip_auto",
    181: "tooltip_history",
    182: "tooltip_system_menu",
    183: "tooltip_hide_window",
    184: "tooltip_save_menu",
    185: "tooltip_exit_scene",
    186: "tooltip_load_menu",
    187: "tooltip_qsave",
    188: "tooltip_qload",
    189: "tooltip_prev_choice",
    190: "tooltip_next_choice",
    191: "tooltip_pin_menu",
    192: "tooltip_window_opacity_1",
    193: "tooltip_window_opacity_2",
    194: "tooltip_fav_voice_add",
    195: "tooltip_fav_voice",
    196: "tooltip_tweet",
    197: "tooltip_tips",
    318: "sys_low_spec_warning",
    328: "unknown_label_1",
    333: "unknown_label_2",
    335: "unknown_label_3",
    541: "config_sample_text",
    690: "misc_dame",
}

# BGM track titles in Music Mode (TEXT.DAT[5..38])
BGM_TITLE_IDS: list[int] = list(range(5, 39))

STORY_START_ID = 1031
STORY_END_ID = 48453  # inclusive; 48454..48455 are staffRollEnter(%d) debug logs

SCENE_MARKER_RE = re.compile(r"^紅月.*_\d+")
RUBY_OPEN_RE = re.compile(r"<\s*r[^<>]*>")
RUBY_CLOSE_RE = re.compile(r"<\s*/\s*r\s*>")


def parse_text_dat(data: bytes) -> list[tuple[int, str]]:
    if not data.startswith(TEXT_DAT_HEADER) or len(data) < 16:
        raise ValueError("Invalid TEXT.DAT header")
    expected = struct.unpack_from("<I", data, 12)[0]
    entries: list[tuple[int, str]] = []
    pos = 16
    while pos + 4 <= len(data):
        idx = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        end = data.index(b"\x00", pos)
        text = data[pos:end].decode("cp932", errors="strict")
        entries.append((idx, text))
        pos = end + 1
    if pos != len(data) or len(entries) != expected:
        raise ValueError(f"TEXT.DAT parse mismatch: got {len(entries)}/{expected}, pos {pos}/{len(data)}")
    for i, (idx, _) in enumerate(entries):
        if idx != i:
            raise ValueError(f"Non-sequential TEXT.DAT index at {i}: got {idx}")
    return entries


def build_text_dat(entries: list[tuple[int, str]]) -> bytes:
    parts: list[bytes] = [TEXT_DAT_HEADER, struct.pack("<I", len(entries))]
    for idx, text in entries:
        encoded = text.encode("cp932", errors="strict")
        if b"\x00" in encoded:
            raise ValueError(f"NUL byte in TEXT.DAT entry {idx}")
        parts.append(struct.pack("<I", idx))
        parts.append(encoded)
        parts.append(b"\x00")
    return b"".join(parts)


def strip_ruby(text: str) -> str:
    """Drop Japanese ruby tags `<rREADING>BASE</r>` -> `BASE`, keeping `<dNNNN>` etc."""
    text = RUBY_OPEN_RE.sub("", text)
    text = RUBY_CLOSE_RE.sub("", text)
    return text


def clean_story_for_llm(text: str) -> str:
    """Drop ruby and join Japanese visual line wraps (`<br>` / `<br>\\u3000`)."""
    out = strip_ruby(text)
    if "<center>" in out:
        return out
    out = out.replace("<br>\u3000", "")
    out = out.replace("<br>", "")
    return out


def discover_speakers(entries: list[tuple[int, str]]) -> set[str]:
    """Identify all speaker names in story range (verified 66 unique speakers)."""
    speakers: set[str] = set()
    for i in range(STORY_START_ID + 1, STORY_END_ID + 1):
        t = entries[i][1]
        prev = re.sub(r"<[^>]+>", "", entries[i - 1][1]).lstrip()
        if prev and prev[0] in "「（『":
            if len(t) <= 22 and not any(c in t for c in "。、「」（）『』<") and not SCENE_MARKER_RE.match(t):
                speakers.add(t)
    return speakers


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()


def extract_workspace(game_dir: pathlib.Path, workspace_dir: pathlib.Path, verify_roundtrip: bool = True) -> dict[str, Any]:
    work_dir = workspace_dir / "work"
    orig_dir = work_dir / "original"
    gt_in_dir = work_dir / "gt_input"
    gt_out_dir = work_dir / "gt_output"
    meta_dir = work_dir / "metadata"
    rep_dir = work_dir / "reports"
    for d in (orig_dir, gt_in_dir, gt_out_dir, meta_dir, rep_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 1. Read pristine archives (read-only on game_dir) and cache original copies
    data_pac = game_dir / "data.pac"
    csv_pac = game_dir / "csv.pac"
    patch_pac = game_dir / "patch.pac"
    for src in (data_pac, csv_pac, patch_pac):
        dst = orig_dir / src.name
        if not dst.exists():
            dst.write_bytes(src.read_bytes())

    raw_text_enc = read_pac2_member(data_pac, "TEXT.DAT", decrypt=False)
    raw_text_dec = decrypt_softpal_table(raw_text_enc)
    raw_sys_ini = read_pac2_member(csv_pac, "SYSTEM.INI", decrypt=False)
    raw_tips_csv = read_pac2_member(csv_pac, "TIPS.CSV", decrypt=False)

    (orig_dir / "TEXT.DAT.dec").write_bytes(raw_text_dec)
    (orig_dir / "SYSTEM.INI").write_bytes(raw_sys_ini)
    (orig_dir / "TIPS.CSV").write_bytes(raw_tips_csv)

    entries = parse_text_dat(raw_text_dec)

    # Roundtrip check on pristine TEXT.DAT & cipher
    rebuilt_dec = build_text_dat(entries)
    if rebuilt_dec != raw_text_dec:
        raise AssertionError("Pristine TEXT.DAT roundtrip mismatch!")
    rebuilt_enc = encrypt_softpal_table(rebuilt_dec)
    if rebuilt_enc != raw_text_enc:
        raise AssertionError("Pristine TEXT.DAT encryption roundtrip mismatch!")

    pac_rt_ok = False
    if verify_roundtrip:
        tmp_pac = work_dir / "reports" / "_verify_data_roundtrip.pac"
        try:
            repack_pac2_with_overrides(data_pac, {"TEXT.DAT": rebuilt_enc}, tmp_pac)
            pac_rt_ok = tmp_pac.read_bytes() == data_pac.read_bytes()
            if not pac_rt_ok:
                raise AssertionError("Pristine data.pac byte-for-byte roundtrip mismatch!")
        finally:
            if tmp_pac.exists():
                tmp_pac.unlink()

    speakers = discover_speakers(entries)

    manifest_files: list[dict[str, Any]] = []
    speaker_counter: Counter[str] = Counter()
    total_gt_records = 0
    total_jp_chars = 0

    def write_json_group(filename: str, kind: str, records: list[dict[str, Any]], meta_rows: list[dict[str, Any]], scene_marker: str | None = None) -> None:
        nonlocal total_gt_records, total_jp_chars
        if not records:
            return
        (gt_in_dir / filename).write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        total_gt_records += len(records)
        for r in records:
            total_jp_chars += len(re.sub(r"<[^>]+>", "", r["message"]))
        manifest_files.append({
            "file": filename,
            "kind": kind,
            "scene_marker": scene_marker,
            "count": len(records),
            "rows": meta_rows,
        })

    # 2. Export 000_ui_system.json
    ui_records: list[dict[str, Any]] = []
    ui_meta: list[dict[str, Any]] = []
    for tid, role in sorted(UI_TRANSLATABLE_IDS.items()):
        raw = entries[tid][1]
        ui_records.append({"message": raw})
        ui_meta.append({"text_id": tid, "name_id": None, "role": role, "raw_text": raw, "preserve_br": True})
    write_json_group("000_ui_system.json", "ui", ui_records, ui_meta)

    # 3. Export 001_bgm_titles.json
    bgm_records: list[dict[str, Any]] = []
    bgm_meta: list[dict[str, Any]] = []
    for tid in BGM_TITLE_IDS:
        raw = entries[tid][1]
        bgm_records.append({"message": raw})
        bgm_meta.append({"text_id": tid, "name_id": None, "role": "bgm_title", "raw_text": raw, "preserve_br": True})
    write_json_group("001_bgm_titles.json", "bgm", bgm_records, bgm_meta)

    # 4. Export 002_tips_csv.json (reference/translatable TIPS term list from csv.pac/TIPS.CSV)
    tips_records: list[dict[str, Any]] = []
    tips_meta: list[dict[str, Any]] = []
    tips_lines = raw_tips_csv.decode("cp932", errors="strict").splitlines()
    tip_idx = 0
    for line_no, ln in enumerate(tips_lines):
        s = ln.strip()
        if not s or s.startswith("//"):
            continue
        cols = s.split(",")
        if len(cols) >= 4:
            term, reading, img_s, img_b = cols[0], cols[1], cols[2], cols[3]
            tips_records.append({"message": term})
            tips_meta.append({
                "tips_index": tip_idx,
                "csv_line": line_no,
                "raw_term": term,
                "reading": reading,
                "img_small": img_s,
                "img_big": img_b,
            })
            tip_idx += 1
    write_json_group("002_tips_csv.json", "tips_csv", tips_records, tips_meta)

    # 5. Export per-scene story JSONs (1031..48453)
    scene_starts: list[tuple[int, str]] = []
    for i in range(STORY_START_ID, STORY_END_ID + 1):
        if SCENE_MARKER_RE.match(entries[i][1]):
            scene_starts.append((i, entries[i][1]))

    file_seq = 3
    empty_markers: list[dict[str, Any]] = []
    for s_idx, (start_id, marker_name) in enumerate(scene_starts):
        end_id = (scene_starts[s_idx + 1][0] - 1) if s_idx + 1 < len(scene_starts) else STORY_END_ID
        records: list[dict[str, Any]] = []
        meta_rows: list[dict[str, Any]] = []

        i = start_id + 1  # skip the scene marker itself (kept locked!)
        while i <= end_id:
            raw_msg = entries[i][1]
            # Check if next entry is a speaker name belonging to this dialogue line
            has_speaker = False
            if i + 1 <= end_id and entries[i + 1][1] in speakers:
                clean_head = re.sub(r"<[^>]+>", "", raw_msg).lstrip()
                clean_tail = re.sub(r"<[^>]+>", "", raw_msg).rstrip()
                if (clean_head and clean_head[0] in "「（『") or (clean_tail and clean_tail[-1] in "」）』"):
                    has_speaker = True

            cleaned_msg = clean_story_for_llm(raw_msg)
            if has_speaker:
                raw_spk = entries[i + 1][1]
                speaker_counter[raw_spk] += 1
                records.append({"name": raw_spk, "message": cleaned_msg})
                meta_rows.append({
                    "text_id": i,
                    "name_id": i + 1,
                    "role": "dialogue",
                    "raw_text": raw_msg,
                    "raw_name": raw_spk,
                    "preserve_br": "<center>" in raw_msg,
                })
                i += 2
            else:
                records.append({"message": cleaned_msg})
                meta_rows.append({
                    "text_id": i,
                    "name_id": None,
                    "role": "narration_or_choice",
                    "raw_text": raw_msg,
                    "preserve_br": "<center>" in raw_msg,
                })
                i += 1

        if not records:
            empty_markers.append({"text_id": start_id, "marker": marker_name})
            continue

        fname = f"{file_seq:03d}_{sanitize_filename(marker_name)}.json"
        write_json_group(fname, "story", records, meta_rows, scene_marker=marker_name)
        file_seq += 1

    # Save manifest & summary report
    manifest = {
        "schema": "softpal-yureaka-manifest/1",
        "game_title": "紅月ゆれる恋あかり",
        "game_title_en": "Akatsuki Yureru Koi Akari",
        "engine": "SOFTPAL / AMUSE CRAFT (PAC v2 + Sv20 + TEXT.DAT)",
        "source_game_dir": str(game_dir),
        "hashes": {
            "data.pac": hashlib.sha256(data_pac.read_bytes()).hexdigest(),
            "csv.pac": hashlib.sha256(csv_pac.read_bytes()).hexdigest(),
            "patch.pac": hashlib.sha256(patch_pac.read_bytes()).hexdigest(),
            "TEXT.DAT.dec": hashlib.sha256(raw_text_dec).hexdigest(),
            "TEXT.DAT.enc": hashlib.sha256(raw_text_enc).hexdigest(),
            "SYSTEM.INI": hashlib.sha256(raw_sys_ini).hexdigest(),
            "TIPS.CSV": hashlib.sha256(raw_tips_csv).hexdigest(),
        },
        "roundtrip_verified": {
            "text_dat_exact": True,
            "text_dat_cipher_exact": True,
            "data_pac_exact": pac_rt_ok,
        },
        "extraction_options": {
            "ruby_dropped": True,
            "story_br_joined": True,
            "keep_honorifics": True,
        },
        "stats": {
            "total_text_dat_entries": len(entries),
            "json_files_exported": len(manifest_files),
            "story_scene_files": sum(1 for f in manifest_files if f["kind"] == "story"),
            "empty_scene_markers": len(empty_markers),
            "total_gt_records": total_gt_records,
            "total_jp_chars_cleaned": total_jp_chars,
            "unique_speakers": len(speaker_counter),
        },
        "speakers": dict(speaker_counter.most_common()),
        "empty_scene_markers": empty_markers,
        "files": manifest_files,
    }
    (meta_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Write concise state report
    summary = {k: v for k, v in manifest.items() if k != "files"}
    (rep_dir / "extraction-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract 紅月ゆれる恋あかり TEXT.DAT to GalTransl JSONs")
    ap.add_argument("--game-dir", type=pathlib.Path, default=pathlib.Path(r"d:\Video_Game\Visual Novel\CRYSTALiA\紅月ゆれる恋あかり"))
    ap.add_argument("--workspace", type=pathlib.Path, default=pathlib.Path(r"d:\Documents\yureaka_en"))
    ap.add_argument("--no-verify-pac", action="store_true")
    args = ap.parse_args(argv)
    summary = extract_workspace(args.game_dir, args.workspace, verify_roundtrip=not args.no_verify_pac)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
