# Translation Style Guide — 紅月ゆれる恋あかり (*Akatsuki Yureru Koi Akari*)

## 1. Core Rules
- **Natural, idiomatic English** preserving character voice, comedic timing, and combat intensity.
- **Honorifics — KEEP**: Retain Japanese honorifics (`-san`, `-kun`, `-chan`, `-sama`, `-senpai`, `-sensei`, `Sensei`, `Onii-chan`, `Onee-san`, etc.) naturally in English (e.g., `Muragaki-sensei`, `Victoria-san`, `Asahi-chan`, `Suzakuin-san`).
- **Ruby / Furigana — DROP**: All `<r...>...</r>` tags are already stripped in `gt_input/`. Do **not** add parenthetical Japanese readings unless required for clarity.
- **Name Order & Reference**: Follow [VNDB v28712](https://vndb.org/v28712) spellings in `terms.json` / `glossary_galtransl.txt` (`Muragaki Iori`, `Suzakuin Momiji`, `Kazamine Setsugekka`, `Kuki Asahi`, `Tobe Ririmu`, `Tennouji Victoria`, `Minamoto Shizuku`, `Arakawa Sonomi`, `Kazamine Keisetsu`, `Sasaki Mikoto`, `Suzakuin Miyako`, `Suzakuin Tsubaki`, `Kuki Takahisa`, `Nakamura Sakura`, `Sassa Naruko`).

## 2. Mandatory Tag & Format Preservation
- Keep the **exact JSON array length**, **record order**, and `"name"` keys of every file in `gt_input/`.
- **Preserve all inline engine tags verbatim** around the translated equivalent:
  - `<dNNNN>...</d>` — clickable TIPS glossary links (105 occurrences). Wrap the translated term inside the exact same `<dNNNN>...</d>` tag!
  - `<sN>...</sN>` — font size override (19 occurrences).
  - `<center>...</center>` — centered narration/headings (4 occurrences).
  - `<c#RRGGBB #RRGGBB>...</c>` — text color tags (if present).
- **Line Wrapping**: Do **not** manually insert `<br>` for normal dialogue wrapping — `tools/text_inject.py` automatically wraps English at pixel-accurate word boundaries using `Barlow Semi Condensed Medium` (24px, ~83 chars/line). Only use `<br>` or `\n` when an intentional paragraph break is needed (keep UI tooltip `<br>` in `000_ui_system.json`).
- **Box Length Budget**: Target **<= 240 English characters** per dialogue box (~3 lines × ~80 chars). Avoid overly verbose expansions that exceed 3 lines.
- **Dialogue Quotes**: Replace Japanese quotes `「...」` with standard ASCII double quotes `"..."`, internal thoughts `（...）` with parentheses `(...)` or italics-free thoughts matching your style, and `『...』` with single quotes `'...'` or `"..."`.
- **ASCII Punctuation**: Standard ASCII (`"`, `'`, `--`, `...`) is preferred; `text_inject.py` automatically normalizes curly quotes, em-dashes, and ellipses to CP932/ASCII-safe characters.
