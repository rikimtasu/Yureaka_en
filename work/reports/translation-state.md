# Translation State — 紅月ゆれる恋あかり (*Akatsuki Yureru Koi Akari*)

**Status**: Complete English Patch Built (100% Script + Engine Hook + All 210 TIPS Cards + 111 Localized UI Graphics) in [`d:\Documents\yureaka_en\dist\`](file:///d:/Documents/yureaka_en/dist/)

| Item | Details |
|---|---|
| **Engine** | SOFTPAL / AMUSE CRAFT (x86 `yureaka.exe` + `dll/Pal.dll`, PAC v2 `PAC/AMUSE`, PGD3 `GE \x00`, runtime `YUR1` overlay on `RVA 0x589f0`) |
| **Script Coverage** | **100.00%** — all 137 script/UI/BGM JSONs (`27,974` rows), including all 175 previously skipped rows across `004_紅月本編_002.json` and `127`–`129` bonus episodes; post-QC verified **0 errors, 0 warnings, 0 four-line overflows, 0 leftover Japanese text, 0 Japanese speakers, 0 unbalanced quotes**. |
| **Runtime Overlay** | `dist/yureaka_en.dat` (`2,835,298 B`, **47,317** entries: 27,958 messages + 19,359 speaker names, 0 split `<d>` TIPS tags, SHA-256 `4db4d4be1d294b29d39340c1bc9f73bf0198f8a5ecec558373538eede79aebd1`). Original `data.pac` stays untouched. |
| **Config & TIPS CSV** | `dist/csv.pac` (`40,044 B`, 14 entries, SHA-256 `4bb81dc0250b8be9e07c2c64fb6e561bfebed8aef9c4e96f833e6eeee4f66290`) with English-calibrated `SYSTEM.INI` (`DefaultSize=28`, `TEXT_DRAW_WIDTH=830`, backlog layout) and translated quoted `TIPS.CSV` (107 entries, Japanese hiragana column 1 preserved for kana tab sorting). |
| **UI & TIPS Graphics** | `dist/patch.pac` (`14,211,882 B`, **322** PGD3 entries, SHA-256 `c13d34c41a5f494cf4fc98cfb9f7e4c4d7899c77490a3f82fa973346bb6df2e9`): byte-exact original `EV102BA.PGD` (1) + **210** rendered English TIPS cards (`TIPS0000B/S`–`TIPS0103B/S`, `TIPS0106B/S`) + **111** localized `system.pac` UI assets (popups, common nav pills, System/Sound/Save/Load/TIPS/Favorite Voice/BGM screens, Title screen glowing English hover states). All 322 `.PGD`s verified lossless and 100% `Pal.dll` LZSS-compliant (`overlaps=0`, `max_long=1027`, `min_dist=5`). |
| **Engine Hook & Fonts** | `dist/version.dll` (`140,800 B`, x86, SHA-256 `7020acf0048e93e25f6b83168c3e51a170f281f98171a11173b60b6c0cb3a24b`), `dist/yureaka_en.ini` (`Log=0`), `dist/en_fonts/` (`BarlowSemiCondensed-Medium.ttf` default + `FiraSansCondensed` & `EncodeSansSemiCondensed`). |
| **Installation** | 1. Back up `csv.pac` and `patch.pac` in the game directory (keep original `data.pac`).<br>2. Copy everything inside `d:\Documents\yureaka_en\dist\` into the game directory, overwriting `csv.pac` and `patch.pac`.<br>3. Launch `yureaka.exe` normally. |
| **Pending Live Check** | Core gameplay text, font metrics, backlog, and window title were live-verified; TIPS popups/menu and localized System/Sound/Save/Load/Title UI screens are ready for final in-game smoke check. |
