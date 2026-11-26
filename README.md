# Akatsuki Yureru Koi Akari (紅月ゆれる恋あかり) — English Translation Patch

Complete English translation patch, runtime engine hook, and asset localization toolkit for **紅月ゆれる恋あかり** (*Akatsuki Yureru Koi Akari*, CRYSTALiA / AMUSE CRAFT, 2020 — [VNDB v28712](https://vndb.org/v28712)).

> **Disclaimer**: This repository contains only English translation scripts, open-source fonts, and open-source build/hooking tools. No copyrighted original game assets are included. You must own a legal copy of the Japanese game to build and use this patch.

---

## Features

- **100% Script Translation**: All 137 script, UI, and BGM files (`27,974` dialogue/system rows + `107` TIPS titles) translated into English with Japanese honorifics preserved and ruby/furigana removed, aligned against a VNDB v28712 glossary.
- **Crash-Free Runtime Text Overlay (`version.dll` + `yureaka_en.dat`)**:
  - Hooks `yureaka.exe`'s single `TEXT.DAT` reader (`RVA 0x589f0`) to serve translated CP932 strings directly from `yureaka_en.dat` (`47,317` entries).
  - Leaves original `data.pac` and `SCRIPT.SRC` 100% untouched—eliminating shifted-offset crashes, length limits, and save-file incompatibilities.
- **Compact Proportional Google Font Typography**:
  - Bundles OFL Google Fonts (`Barlow Semi Condensed Medium` default, plus `Fira Sans Condensed` and `Encode Sans Semi Condensed`).
  - Hooks `Pal.dll` delay-load (`CreateFontA`, `PalFontSetType`, `PalFontBegin`, `PalFontSetFontSize`, `PalFontGetSize`) and calibrates `SYSTEM.INI` + GDI `GetGlyphOutlineA` pixel word-wrapping (`795px` wrap width, zero descender clipping, clean backlog layout, localized English window title).
- **Complete UI & TIPS Localization (`dist/patch.pac` + `dist/csv.pac`)**:
  - Lossless Softpal PAC v2 (`PAC/AMUSE`) and PGD3 (`GE \x00`, `Pal.dll`-compliant non-overlapping LZSS) codecs.
  - Programmatically renders all **210 English TIPS cards** (`105 Big` + `105 Small`), updates `TIPS.CSV` (preserving column 1 kana sorting), and localizes **111 `system.pac` UI graphics** (confirmation popups, common navigation pills, System/Sound/Save/Load/TIPS/Favorite Voice/Music Mode screens, and glowing English Title Screen hover states).

---

## Building from Source

### Prerequisites
- A legal copy of **紅月ゆれる恋あかり** (`yureaka.exe`, `data.pac`, `csv.pac`, `patch.pac`, `tips.pac`, `system.pac`).
- Python 3.10+ with `pillow` and `numpy` (`pip install pillow numpy`).
- Visual Studio (MSVC x86 toolset) to compile `hook/version.dll`.

### Build Steps
1. **Extract pristine metadata & original archives** (reads your game directory strictly read-only):
   ```powershell
   python tools/text_extract.py --game-dir "D:\Path\To\紅月ゆれる恋あかり" --workspace .
   ```
2. **Compile the x86 proxy hook** (`hook/version.dll`):
   ```powershell
   cmd /c hook\build.bat
   ```
3. **Render all 210 TIPS cards & 111 localized UI `.PGD` assets** (update `GAME_DIR` in `tools/render_tips.py` and `tools/render_ui.py` if your game path differs):
   ```powershell
   python tools/render_tips.py
   python tools/render_ui.py
   ```
4. **Run QA lint & assemble `dist/`**:
   ```powershell
   python tools/qa_lint.py
   python tools/build_patch.py --strict-complete
   ```

---

## Installing the Built Patch

1. In your **紅月ゆれる恋あかり** installation folder, back up your original `csv.pac` and `patch.pac`. Keep your original `data.pac` untouched.
2. Copy everything inside `dist/` (`version.dll`, `yureaka_en.ini`, `yureaka_en.dat`, `csv.pac`, `patch.pac`, and `en_fonts/`) into the game folder, overwriting `csv.pac` and `patch.pac`.
3. Launch `yureaka.exe` normally.

### Changing the Font
Edit `yureaka_en.ini` next to `yureaka.exe` to switch between the bundled Google Fonts (`Barlow Semi Condensed Medium`, `Fira Sans Condensed`, `Encode Sans Semi Condensed`) or adjust `CharSpacingDelta` / `SpaceWidthPercent`.

---

## Repository Layout

| Path | Description |
|---|---|
| `tools/softpal_pac.py` | Softpal PAC v2 (`PAC/AMUSE`) unpacker/repacker with byte-exact SHA-256 roundtrip and `$`-table cipher |
| `tools/softpal_pgd.py` | Softpal PGD3 (`GE \x00`, method 3) lossless decoder & `Pal.dll`-compliant non-overlapping LZSS encoder |
| `tools/text_extract.py` | Extracts `TEXT.DAT` & `TIPS.CSV` into GalTransl JSONs + offset manifest |
| `tools/text_inject.py` | Compiles translated JSONs into `yureaka_en.dat` with Windows GDI pixel word-wrapping and atomic `<dNNNN>` tag handling |
| `tools/qa_lint.py` | Strict QA linter validating tags, CP932 encodability, and formatting across all script JSONs |
| `tools/render_tips.py` | Renders all 210 English TIPS `.PGD` cards (Big + Small) |
| `tools/render_ui.py` | Renders 111 localized `system.pac` UI `.PGD` graphics |
| `tools/build_patch.py` | End-to-end builder assembling `dist/` (`yureaka_en.dat`, `csv.pac`, `patch.pac`, `version.dll`, `yureaka_en.ini`, `en_fonts/`) |
| `tools/extract_glossary.py`, `tools/build_glossary.py` | Glossary extraction & VNDB v28712 term builder |
| `hook/` | x86 `version.dll` C++ proxy hook (`version_proxy.cpp`, `version.def`, `build.bat`, `yureaka_en.ini`) |
| `assets/fonts/` | Bundled OFL Google Fonts TTFs |
| `work/gt_output/` | Complete translated GalTransl JSONs (138 files) |
| `work/glossary/` | VNDB-referenced character/term glossary & style guide |
| `work/reports/` | QA lint, build, and translation state reports |
