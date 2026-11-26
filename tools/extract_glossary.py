#!/usr/bin/env python3
"""Extract character & terminology glossary candidates from TEXT.DAT, TIPS.CSV, ruby tags, and VNDB v28712.

Outputs:
- `work/glossary/glossary_raw_candidates.json` (structured full dataset with frequencies & context)
- `work/glossary/vndb_v28712.json` (cached VNDB v28712 reference)
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from text_extract import parse_text_dat  # noqa: E402

RUBY_PAIR_RE = re.compile(r"<\s*r([^<>]+?)>(.*?)<\s*/\s*r\s*>")
TIPS_LINK_RE = re.compile(r"<d(\d{4})>(.*?)</d>")


def main() -> int:
    workspace = pathlib.Path(r"d:\Documents\yureaka_en")
    work = workspace / "work"
    gloss_dir = work / "glossary"
    gloss_dir.mkdir(parents=True, exist_ok=True)

    # Copy cached VNDB reference into workspace
    vndb_scratch = pathlib.Path(r"C:\Users\User\.gemini\antigravity\brain\c5222213-9c3d-46be-a29a-36ce98ab0881\scratch\vndb_v28712.json")
    vndb_dst = gloss_dir / "vndb_v28712.json"
    if vndb_scratch.exists() and not vndb_dst.exists():
        vndb_dst.write_bytes(vndb_scratch.read_bytes())
    vndb_data = json.loads(vndb_dst.read_text(encoding="utf-8"))

    manifest = json.loads((work / "metadata" / "manifest.json").read_text(encoding="utf-8"))
    entries = parse_text_dat((work / "original" / "TEXT.DAT.dec").read_bytes())
    tips_raw = (work / "original" / "TIPS.CSV").read_bytes().decode("cp932", errors="strict")

    # 1. Parse TIPS.CSV (107 glossary terms)
    tips_list = []
    for ln in tips_raw.splitlines():
        s = ln.strip()
        if not s or s.startswith("//"):
            continue
        cols = s.split(",")
        if len(cols) >= 4:
            tips_list.append({
                "id": f"d{len(tips_list):04d}",
                "jp": cols[0],
                "reading": cols[1],
                "img_small": cols[2],
                "img_big": cols[3],
                "link_texts": [],
                "occurrences": 0,
            })

    # Scan TEXT.DAT for <dNNNN> link texts, ruby-annotated terms, and full-text frequencies
    ruby_counts: Counter[tuple[str, str]] = Counter()
    ruby_samples: dict[tuple[str, str], str] = {}
    all_story_text = [t for idx, t in entries if 1031 <= idx <= 48453]
    joined_story = "\n".join(all_story_text)

    for t in all_story_text:
        for m in TIPS_LINK_RE.finditer(t):
            tid = int(m.group(1))
            if tid < len(tips_list):
                lt = re.sub(r"<[^>]+>", "", m.group(2))
                if lt not in tips_list[tid]["link_texts"]:
                    tips_list[tid]["link_texts"].append(lt)
        for m in RUBY_PAIR_RE.finditer(t):
            reading = m.group(1).strip()
            base_txt = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            if base_txt:
                key = (base_txt, reading)
                ruby_counts[key] += 1
                if key not in ruby_samples:
                    ruby_samples[key] = re.sub(r"<[^>]+>", "", t)[:80]

    for tip in tips_list:
        tip["occurrences"] = joined_story.count(tip["jp"])

    # 2. Extract notable ruby-annotated terms (katakana readings, blade arts, special nouns)
    ruby_terms = [
        {"jp": base_txt, "reading": reading, "count": cnt, "sample": ruby_samples[(base_txt, reading)]}
        for (base_txt, reading), cnt in ruby_counts.most_common()
    ]

    # 3. Extract character occurrences from speakers + VNDB
    speakers = manifest["speakers"]
    vndb_chars = []
    for c in vndb_data["characters"]["results"]:
        roles = [v["role"] for v in c.get("vns", []) if v["id"] == "v28712"]
        orig = c.get("original") or ""
        parts = orig.split()
        surname_jp = parts[0] if len(parts) >= 2 else ""
        given_jp = parts[1] if len(parts) >= 2 else orig
        vndb_chars.append({
            "vndb_id": c["id"],
            "role": ",".join(roles),
            "name_en_vndb": c["name"],
            "original_jp": orig,
            "surname_jp": surname_jp,
            "given_jp": given_jp,
            "sex": (c.get("sex") or [None])[0],
            "speaker_count": speakers.get(given_jp, speakers.get(orig.replace(" ", ""), 0)),
            "description": c.get("description") or "",
        })

    out = {
        "vn": vndb_data["vn"]["results"][0],
        "vndb_characters": vndb_chars,
        "all_speakers": speakers,
        "tips_terms": tips_list,
        "ruby_terms": ruby_terms,
    }
    (gloss_dir / "glossary_raw_candidates.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"VNDB characters: {len(vndb_chars)}")
    print(f"All speakers:    {len(speakers)}")
    print(f"TIPS terms:      {len(tips_list)}")
    print(f"Ruby pairs:      {len(ruby_terms)}")
    print("\n=== All 107 TIPS terms ===")
    for t in tips_list:
        print(f"  {t['id']} ({t['occurrences']:4d}x): {t['jp']} [{t['reading']}]")
    print("\n=== Top 50 Ruby-annotated terms ===")
    for r in ruby_terms[:50]:
        print(f"  {r['count']:3d}x: {r['jp']} 《{r['reading']}》")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
