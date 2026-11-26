#!/usr/bin/env python3
"""QA linter for `work/gt_output/` translated JSONs prior to building the English patch."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from text_inject import (  # noqa: E402
    PixelWordWrapper,
    extract_protected_tags,
    is_mostly_ascii,
    normalize_english_text,
)


def lint_workspace(
    workspace: pathlib.Path,
    *,
    font_file: str = "BarlowSemiCondensed-Medium.ttf",
    font_size: int = 28,
    max_width_px: int = 795,
    max_lines: int = 3,
) -> dict:
    work = workspace / "work"
    manifest = json.loads((work / "metadata" / "manifest.json").read_text(encoding="utf-8"))
    gt_out = work / "gt_output"
    wrapper = PixelWordWrapper(workspace / "assets" / "fonts" / font_file, font_size=font_size, max_width_px=max_width_px, max_lines=max_lines)

    errors: list[dict] = []
    warnings: list[dict] = []
    checked_files = 0
    checked_rows = 0

    for fmeta in manifest["files"]:
        if fmeta["kind"] == "tips_csv":
            continue
        p = gt_out / fmeta["file"]
        if not p.exists():
            continue
        checked_files += 1
        try:
            rows = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append({"file": fmeta["file"], "kind": "invalid_json", "error": str(e)})
            continue
        if not isinstance(rows, list) or len(rows) != fmeta["count"]:
            errors.append({"file": fmeta["file"], "kind": "count_mismatch", "expected": fmeta["count"], "actual": len(rows) if isinstance(rows, list) else None})
            continue

        for r_idx, (rec, mrow) in enumerate(zip(rows, fmeta["rows"])):
            checked_rows += 1
            msg = rec.get("message")
            if not isinstance(msg, str) or not msg.strip():
                errors.append({"file": fmeta["file"], "row": r_idx, "kind": "empty_message"})
                continue
            orig_tags = extract_protected_tags(mrow["raw_text"])
            new_tags = extract_protected_tags(msg)
            if orig_tags != new_tags:
                errors.append({
                    "file": fmeta["file"], "row": r_idx, "kind": "tag_mismatch",
                    "expected": orig_tags, "actual": new_tags, "message": msg[:120],
                })
            if mrow["name_id"] is not None:
                if "name" not in rec or not isinstance(rec["name"], str) or not rec["name"].strip():
                    errors.append({"file": fmeta["file"], "row": r_idx, "kind": "missing_name"})
            if is_mostly_ascii(msg):
                norm = normalize_english_text(msg)
                try:
                    norm.encode("cp932", errors="strict")
                except UnicodeEncodeError as e:
                    errors.append({"file": fmeta["file"], "row": r_idx, "kind": "cp932_encode", "error": str(e), "message": norm[:120]})
                if fmeta["kind"] == "story" and not mrow.get("preserve_br", False):
                    wrapped, n_lines = wrapper.wrap(norm)
                    if n_lines > max_lines:
                        warnings.append({
                            "file": fmeta["file"], "row": r_idx, "kind": "line_overflow",
                            "lines": n_lines, "message": wrapped,
                        })
            else:
                try:
                    msg.encode("cp932", errors="strict")
                except UnicodeEncodeError as e:
                    errors.append({"file": fmeta["file"], "row": r_idx, "kind": "cp932_encode", "error": str(e), "message": msg[:120]})

    report = {
        "ok": len(errors) == 0,
        "checked_files": checked_files,
        "checked_rows": checked_rows,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors[:100],
        "warnings": warnings[:100],
    }
    (work / "reports" / "qa-lint-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="QA lint work/gt_output JSONs")
    ap.add_argument("--workspace", type=pathlib.Path, default=pathlib.Path(r"d:\Documents\yureaka_en"))
    ap.add_argument("--font", default="BarlowSemiCondensed-Medium.ttf")
    ap.add_argument("--font-size", type=int, default=24)
    ap.add_argument("--max-width", type=int, default=810)
    ap.add_argument("--max-lines", type=int, default=3)
    args = ap.parse_args()
    rep = lint_workspace(args.workspace, font_file=args.font, font_size=args.font_size, max_width_px=args.max_width, max_lines=args.max_lines)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
