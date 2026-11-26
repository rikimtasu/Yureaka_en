#!/usr/bin/env python3
"""Programmatically localize all essential Japanese UI graphics from `system.pac`
into `work/pgd_overrides/*.PGD`, preserving exact PgdMeta, alpha channels, pill shapes,
and color palettes.

Covers ~108 UI .PGD files:
  - Confirmation popups (POP_STRING, POP_YES, POP_NO, POP_UNLOCK)
  - Common nav buttons (COM_BTN_EXIT/GAMEEND/TITLE/RESET/WINDOW_RESTORE + _LO/_SA/_EX)
  - System config screen (SYS_BASE, SYS_TITLE_SCREENMODE, SYS_BTN_*, SYS_SCUT_MENU00..11)
  - Sound config screen (SOUND_BASE, SOUND_UNIT00..10 + OTHER Mute/Other labels)
  - Save/Load screens (SAVE_BASE, LOAD_BASE, SAVE_BTN_*, LOAD_BTN_*)
  - TIPS screen (TIPS_BASE, TIPS_S_*, TIPS_I00, TIPS_T00)
  - Favorite Voice & BGM screens (FAVORITE_BASE, FAV_BTN_*, BGM_BTN_*)
  - Title screen hover/active states (TITLE_BTN_*)
"""
from __future__ import annotations

import pathlib
import sys
from typing import Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from softpal_pac import read_pac2_index  # noqa: E402
from softpal_pgd import PgdMeta, decode_pgd, encode_pgd  # noqa: E402

WORKSPACE = pathlib.Path(r"d:\Documents\yureaka_en")
GAME_DIR = pathlib.Path(r"d:\Video_Game\Visual Novel\CRYSTALiA\紅月ゆれる恋あかり")
SYSTEM_PAC = GAME_DIR / "system.pac"
OUT_PGD = WORKSPACE / "work" / "pgd_overrides"
PREVIEW_DIR = WORKSPACE / "work" / "ui_preview"

FONT_MED = WORKSPACE / "assets" / "fonts" / "BarlowSemiCondensed-Medium.ttf"
FONT_FIRA = WORKSPACE / "assets" / "fonts" / "FiraSansCondensed-Regular.ttf"
FONT_FIRA_MED = WORKSPACE / "assets" / "fonts" / "FiraSansCondensed-Medium.ttf"


def load_font(path: pathlib.Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def fit_font(
    draw: ImageDraw.ImageDraw,
    lines: Sequence[str],
    font_path: pathlib.Path,
    max_w: int,
    max_size: int,
    min_size: int = 10,
) -> ImageFont.FreeTypeFont:
    for sz in range(max_size, min_size - 1, -1):
        f = load_font(font_path, sz)
        if all(draw.textlength(ln, font=f) <= max_w for ln in lines):
            return f
    return load_font(font_path, min_size)


def draw_glow_text(
    canvas: Image.Image,
    pos: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    glow_color: tuple[int, int, int, int],
    glow_radius: float = 2.0,
    glow_passes: int = 2,
    anchor: str = "la",
) -> None:
    """Draw crisp text with a soft colored glow matching Softpal's UI styling."""
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text(pos, text, font=font, fill=glow_color, anchor=anchor)
    glow = layer.filter(ImageFilter.GaussianBlur(radius=glow_radius))
    for _ in range(glow_passes):
        canvas.alpha_composite(glow)
    d_top = ImageDraw.Draw(canvas)
    d_top.text(pos, text, font=font, fill=fill, anchor=anchor)


def draw_centered_lines(
    im: Image.Image,
    box: tuple[int, int, int, int],
    lines: Sequence[str],
    font_path: pathlib.Path,
    fill: tuple[int, int, int, int],
    max_size: int = 20,
    min_size: int = 10,
    line_gap: int = 1,
    glow_color: tuple[int, int, int, int] | None = None,
    glow_radius: float = 1.4,
) -> None:
    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0
    draw = ImageDraw.Draw(im)
    f = fit_font(draw, lines, font_path, max_w=w - 10, max_size=max_size, min_size=min_size)
    # Measure actual tight heights via textbbox
    heights = []
    for ln in lines:
        bb = draw.textbbox((0, 0), ln, font=f)
        heights.append(bb[3] - bb[1])
    total_h = sum(heights) + line_gap * (len(lines) - 1)
    # Shrink if vertically too tall
    while total_h > h - 4 and f.size > min_size:
        f = load_font(font_path, f.size - 1)
        heights = [draw.textbbox((0, 0), ln, font=f)[3] - draw.textbbox((0, 0), ln, font=f)[1] for ln in lines]
        total_h = sum(heights) + line_gap * (len(lines) - 1)

    cur_y = y0 + (h - total_h) / 2.0
    cx = (x0 + x1) / 2.0
    for ln, lh in zip(lines, heights):
        bb = draw.textbbox((0, 0), ln, font=f)
        tw = bb[2] - bb[0]
        tx = int(round(cx - tw / 2.0 - bb[0]))
        ty = int(round(cur_y - bb[1]))
        if glow_color is not None:
            draw_glow_text(im, (tx, ty), ln, f, fill, glow_color, glow_radius=glow_radius, glow_passes=1)
        else:
            draw.text((tx, ty), ln, font=f, fill=fill)
        cur_y += lh + line_gap


def clean_state_strip_interior(
    orig: Image.Image,
    n_states: int,
    margin_x: int = 8,
    margin_y: int = 5,
    sample_x: int | None = None,
) -> tuple[Image.Image, list[tuple[int, int, int, int]]]:
    """Clean text out of a multi-state vertical button sprite by filling each state's inner rect
    with the clean background color sampled inside that state's rounded pill/rectangle.
    Returns (cleaned_image, list_of_sampled_bg_rgba).
    """
    arr = np.array(orig.convert("RGBA"))
    h, w, _ = arr.shape
    sh = h // n_states
    bgs: list[tuple[int, int, int, int]] = []
    sx = sample_x if sample_x is not None else min(w - 6, max(5, margin_x + 2))
    for i in range(n_states):
        y0 = i * sh
        y1 = y0 + sh
        # Sample median of a clean inner vertical strip near left edge (away from centered text)
        sy0 = y0 + margin_y
        sy1 = y1 - margin_y
        # Check left & right margins; pick whichever has lower variance (no text)
        left_patch = arr[sy0:sy1, sx : min(w - 2, sx + 4)]
        right_patch = arr[sy0:sy1, max(2, w - sx - 4) : w - sx]
        l_var = float(left_patch.var()) if left_patch.size else 1e9
        r_var = float(right_patch.var()) if right_patch.size else 1e9
        patch = left_patch if l_var <= r_var else right_patch
        bg = tuple(int(round(v)) for v in np.median(patch.reshape(-1, 4), axis=0))
        bgs.append(bg)
        # Replace ALL interior pixels (including dark semi-transparent states with alpha=128..179!)
        # while preserving transparent exterior pixels outside rounded corners (alpha <= 20).
        sub = arr[y0 + margin_y : y1 - margin_y, margin_x : w - margin_x]
        mask = sub[:, :, 3] > 20
        sub[mask, 0] = bg[0]
        sub[mask, 1] = bg[1]
        sub[mask, 2] = bg[2]
        sub[mask, 3] = bg[3]
    return Image.fromarray(arr, mode="RGBA"), bgs


def pick_text_color_for_bg(bg: tuple[int, int, int, int], style: str = "blue") -> tuple[int, int, int, int]:
    """Choose crisp, high-contrast Softpal-style text color based on state background luminance/hue."""
    r, g, b, a = bg
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    if a < 50:
        # Transparent / dark backdrop (e.g., disabled/dark top row in 4-state buttons)
        return (235, 240, 248, 255)
    if lum < 95:
        # Dark slate / dark maroon / dark gray
        return (245, 248, 252, 255)
    if r > 220 and g > 220 and b > 220:
        # Off-white / white normal state
        if style == "pink":
            return (220, 68, 126, 255)
        return (72, 110, 195, 255)
    if g > 200 and b > 220 and r < 110:
        # Bright cyan hover state
        return (255, 255, 255, 255)
    if r > 210 and g < 110 and b > 100:
        # Bright magenta-pink hover state (Save screen)
        return (255, 255, 255, 255)
    if r > 190 and g > 140 and b > 170 and style == "pink":
        # Pale pink disabled state
        return (248, 232, 240, 255)
    if b > 190 and r > 140 and g > 150:
        # Lavender / periwinkle disabled state
        return (235, 242, 255, 255)
    return (255, 255, 255, 255)


def render_multistate_button(
    orig: Image.Image,
    n_states: int,
    lines: Sequence[str],
    *,
    style: str = "blue",
    margin_x: int = 8,
    margin_y: int = 4,
    max_size: int = 20,
    min_size: int = 10,
    font_path: pathlib.Path = FONT_MED,
    state_colors: Sequence[tuple[int, int, int, int]] | None = None,
    per_state_lines: Sequence[Sequence[str]] | None = None,
    x_offset_box: tuple[int, int] | None = None,
) -> Image.Image:
    w, h = orig.size
    sh = h // n_states
    if x_offset_box is not None:
        # Special case like LOCK button with an icon on the left
        arr = np.array(orig.convert("RGBA"))
        bx0, bx1 = x_offset_box
        bgs = []
        for i in range(n_states):
            y0, y1 = i * sh, (i + 1) * sh
            patch = arr[y0 + 3 : y1 - 3, bx1 - 6 : bx1 - 2]
            bg = tuple(int(round(v)) for v in np.median(patch.reshape(-1, 4), axis=0))
            bgs.append(bg)
            arr[y0 + 2 : y1 - 2, bx0:bx1] = bg
        im = Image.fromarray(arr, mode="RGBA")
    else:
        im, bgs = clean_state_strip_interior(orig, n_states, margin_x=margin_x, margin_y=margin_y)
        bx0, bx1 = margin_x, w - margin_x

    for i in range(n_states):
        y0, y1 = i * sh, (i + 1) * sh
        st_lines = per_state_lines[i] if per_state_lines else lines
        col = state_colors[i] if state_colors else pick_text_color_for_bg(bgs[i], style=style)
        # Subtle shadow/glow on bright cyan/pink hover states for crisp readability
        bg = bgs[i]
        glow = None
        if (bg[1] > 200 and bg[2] > 220 and bg[0] < 110) or (bg[0] > 210 and bg[1] < 110):
            glow = (40, 80, 120, 110) if style == "blue" else (140, 20, 70, 110)
        draw_centered_lines(
            im,
            (bx0, y0 + 1, bx1, y1 - 1),
            st_lines,
            font_path=font_path,
            fill=col,
            max_size=max_size,
            min_size=min_size,
            glow_color=glow,
        )
    return im


def render_pop_string(orig: Image.Image) -> Image.Image:
    w, h = orig.size  # 423 x 504 (18 rows x 28px)
    prompts = [
        "Quit the game?",
        "Return to the title screen?",
        "Reset all settings to default?",
        "Quick Save your progress?",
        "Quick Load saved data?",
        "Save to this slot?",
        "Load this save data?",
        "Overwrite this save data?",
        "Copy this save data?",
        "Move this save data?",
        "Delete this save data?",
        "Jump to the next choice?",
        "Return to the previous choice?",
        "Delete all save data?",
        "Really delete all save data?",
        "Delete the selected voice?",
        "Delete all checked voices?",
        "Jump back to the selected line?",
    ]
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    row_h = h // len(prompts)  # 28
    draw = ImageDraw.Draw(out)
    for idx, text in enumerate(prompts):
        f = fit_font(draw, [text], FONT_MED, max_w=w - 24, max_size=21, min_size=14)
        bb = draw.textbbox((0, 0), text, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        tx = int(round((w - tw) / 2.0 - bb[0]))
        ty = int(round(idx * row_h + (row_h - th) / 2.0 - bb[1]))
        draw_glow_text(
            out,
            (tx, ty),
            text,
            f,
            fill=(255, 255, 255, 255),
            glow_color=(95, 140, 235, 220),
            glow_radius=2.2,
            glow_passes=2,
        )
    return out


def render_pop_unlock(orig: Image.Image) -> Image.Image:
    w, h = orig.size  # 423 x 43
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(out)
    line1 = "Unlock all extra content?"
    line2 = "(Warning: Once unlocked, this cannot be undone)"
    f1 = fit_font(draw, [line1], FONT_MED, max_w=w - 16, max_size=22, min_size=14)
    f2 = fit_font(draw, [line2], FONT_FIRA, max_w=w - 12, max_size=13, min_size=10)
    bb1 = draw.textbbox((0, 0), line1, font=f1)
    bb2 = draw.textbbox((0, 0), line2, font=f2)
    tx1 = int(round((w - (bb1[2] - bb1[0])) / 2.0 - bb1[0]))
    tx2 = int(round((w - (bb2[2] - bb2[0])) / 2.0 - bb2[0]))
    draw_glow_text(out, (tx1, 2 - bb1[1]), line1, f1, (255, 255, 255, 255), (220, 65, 125, 230), glow_radius=2.2, glow_passes=2)
    draw_glow_text(out, (tx2, 27 - bb2[1]), line2, f2, (255, 245, 250, 255), (210, 55, 115, 220), glow_radius=1.6, glow_passes=2)
    return out


def render_sys_base(orig: Image.Image) -> Image.Image:
    im = orig.copy().convert("RGBA")
    arr = np.array(im)
    bg = tuple(int(v) for v in arr[150, 500])  # [51, 51, 69, 217]

    # Erase left column Japanese labels + descriptions (keeping MIN/MAX at x>=290, sample box at y=565..606)
    arr[170:468, 55:312] = bg
    arr[470:560, 55:278] = bg
    # Erase bottom note (y=614..639, x=55..650)
    arr[614:639, 55:650] = bg
    # Erase right top header (y=118..156, x=690..1120) — keeps F1..F12 at y>=162 untouched!
    arr[118:156, 690:1120] = bg
    # Erase right bottom header + 2-column sub-click labels (y=402..630, x=690..1160)
    arr[402:630, 690:1160] = bg
    im = Image.fromarray(arr, mode="RGBA")

    f_hdr = load_font(FONT_MED, 21)
    f_sub = load_font(FONT_FIRA, 12)
    f_rad = load_font(FONT_MED, 19)
    f_note = load_font(FONT_FIRA, 13)
    glow_blue = (70, 105, 215, 210)
    white = (255, 255, 255, 255)
    sub_col = (232, 236, 246, 255)

    left_items = [
        (173, "Visual Effects", "Turn Off if display performance feels slow."),
        (223, "Skip Mode", "Choose which messages can be skipped."),
        (272, "Stop Auto on Choice", "Cancel Auto mode when a choice appears."),
        (322, "Stop Skip on Choice", "Cancel Skip mode when a choice appears."),
        (373, "Auto-Hide Cursor", "Set delay before hiding the mouse cursor."),
        (423, "Font Style", "Select the font used in the message window."),
        (473, "Text Speed", "Adjust message display speed."),
        (523, "Auto Speed", "Adjust Auto mode advance speed."),
    ]
    draw = ImageDraw.Draw(im)
    for y, title, desc in left_items:
        draw_glow_text(im, (62, y), title, f_hdr, white, glow_blue, glow_radius=1.8, glow_passes=2)
        draw.text((64, y + 23), desc, font=f_sub, fill=sub_col)

    draw_glow_text(
        im,
        (62, 619),
        "* Adjust message window opacity via the Window menu slider.",
        f_note,
        white,
        glow_blue,
        glow_radius=1.2,
        glow_passes=1,
    )

    # Right top: Shortcut Keys
    draw_glow_text(im, (698, 120), "Shortcut Keys", f_hdr, white, glow_blue, glow_radius=1.8, glow_passes=2)
    draw.text((700, 143), "Assign functions to the F1\u2013F12 keys.", font=f_sub, fill=sub_col)

    # Right bottom: Right-Click Action
    draw_glow_text(im, (698, 405), "Right-Click Action", f_hdr, white, glow_blue, glow_radius=1.8, glow_passes=2)
    draw.text((700, 428), "Assign a function to right-clicking.", font=f_sub, fill=sub_col)

    right_left_col = [
        (448, "Save"),
        (487, "Skip"),
        (527, "Replay Voice"),
        (566, "System"),
        (605, "None"),
    ]
    right_right_col = [
        (448, "Load"),
        (487, "Auto Play"),
        (527, "Backlog"),
        (566, "Hide Text"),
    ]
    for y, lbl in right_left_col:
        draw_glow_text(im, (766, y), lbl, f_rad, white, glow_blue, glow_radius=1.5, glow_passes=2)
    for y, lbl in right_right_col:
        draw_glow_text(im, (990, y), lbl, f_rad, white, glow_blue, glow_radius=1.5, glow_passes=2)

    return im


def render_sys_title_screenmode(orig: Image.Image) -> Image.Image:
    w, h = orig.size  # 151 x 41
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    f_hdr = load_font(FONT_MED, 19)
    f_sub = load_font(FONT_FIRA, 11)
    draw_glow_text(out, (2, 1), "Display Mode", f_hdr, (255, 255, 255, 255), (70, 105, 215, 210), glow_radius=1.5, glow_passes=2)
    ImageDraw.Draw(out).text((3, 24), "Switch screen display mode.", font=f_sub, fill=(235, 240, 250, 255))
    return out


def render_sound_base(orig: Image.Image) -> Image.Image:
    im = orig.copy().convert("RGBA")
    arr = np.array(im)
    bg = tuple(int(v) for v in arr[300, 600])  # [51, 51, 69, 217]

    # Erase Japanese volume titles (keeping MIN at y+16 and ▶ arrows intact!) and ミュート labels (keeping MAX below)
    vol_rows = [
        (126, "Master Volume", 125, 141),
        (179, "BGM Volume", 178, 194),
        (232, "SE Volume", 231, 247),
        (285, "System SE Volume", 284, 300),
        (338, "Voice Volume", 337, 353),
        (391, "BGM During Voice", 390, 406),
    ]
    for _y, _lbl, ey0, ey1 in vol_rows:
        arr[ey0:ey1, 48:304] = bg
        arr[ey0:ey1, 310:366] = bg  # ミュート above MAX

    # Erase 3 bottom toggle labels
    bottom_rows = [
        (447, "Voice Skip"),
        (515, "Voice Auto-Pan"),
        (583, "System Voice"),
    ]
    for y, _lbl in bottom_rows:
        arr[y - 4 : y + 20, 30:260] = bg

    im = Image.fromarray(arr, mode="RGBA")
    f_vol = load_font(FONT_MED, 16)
    f_mute = load_font(FONT_FIRA, 12)
    f_bot = load_font(FONT_MED, 18)
    glow_blue = (70, 105, 215, 210)
    white = (255, 255, 255, 255)
    draw = ImageDraw.Draw(im)

    for y, lbl, _ey0, _ey1 in vol_rows:
        draw_glow_text(im, (52, y - 2), lbl, f_vol, white, glow_blue, glow_radius=1.4, glow_passes=2)
        draw.text((322, y + 1), "Mute", font=f_mute, fill=(235, 240, 248, 255))

    for y, lbl in bottom_rows:
        draw_glow_text(im, (34, y - 2), lbl, f_bot, white, glow_blue, glow_radius=1.6, glow_passes=2)

    return im


def render_sound_unit(orig: Image.Image, is_other: bool = False) -> Image.Image:
    """Cleanly replace 'ミュート' -> 'Mute' in top-right dark strip (and 'その他' -> 'Other' on OTHER)."""
    im = orig.copy().convert("RGBA")
    arr = np.array(im)
    # Sample clean dark strip next to ミュート at (x=212, y=12..28)
    bg_mute = tuple(int(round(v)) for v in np.median(arr[12:28, 210:222].reshape(-1, 4), axis=0))
    arr[11:29, 232:288] = bg_mute
    if is_other:
        # Erase ruby 'た' + 'その他' (x=208..290, y=38..84) using flat card bg (keeps MAX at y>=86 intact!)
        arr[38:84, 208:290] = bg_mute
    im = Image.fromarray(arr, mode="RGBA")
    draw = ImageDraw.Draw(im)
    draw.text((248, 12), "Mute", font=load_font(FONT_FIRA, 12), fill=(235, 240, 248, 255))
    if is_other:
        draw_glow_text(
            im,
            (226, 52),
            "Other",
            load_font(FONT_MED, 24),
            (255, 255, 255, 255),
            (40, 60, 120, 180),
            glow_radius=1.4,
            glow_passes=1,
        )
    return im


def render_save_or_load_base(orig: Image.Image, is_save: bool) -> Image.Image:
    """Seamlessly localize the right-side confirmation checkbox labels & vertical note
    on SAVE_BASE (maroon gradient) and LOAD_BASE (slate).
    """
    im = orig.copy().convert("RGBA")
    arr = np.array(im)
    # Copy clean background per scanline from x=1048..1056 into x=1066..1276 for y=402..655
    for y in range(402, 656):
        sample = arr[y, 1046:1058]
        col = np.median(sample, axis=0).astype(np.uint8)
        arr[y, 1066:1278] = col
    im = Image.fromarray(arr, mode="RGBA")

    labels = [
        (408, "Quick Save"),
        (440, "Quick Load"),
        (472, "Save"),
        (504, "Load"),
        (536, "Overwrite"),
        (568, "Copy Data"),
        (600, "Move Data"),
        (632, "Delete Data"),
    ]
    glow = (175, 40, 90, 220) if is_save else (70, 105, 215, 220)
    f_lbl = load_font(FONT_MED, 18)
    for y, lbl in labels:
        draw_glow_text(im, (1080, y - 1), lbl, f_lbl, (255, 255, 255, 255), glow, glow_radius=1.5, glow_passes=2)

    # Render clean vertical rotated note along right edge (x=1236..1268, y=408..650)
    note_img = Image.new("RGBA", (244, 34), (0, 0, 0, 0))
    f_note = load_font(FONT_FIRA, 13)
    draw_glow_text(
        note_img,
        (4, 8),
        "* Toggle confirm dialogs on left",
        f_note,
        (255, 255, 255, 255),
        glow,
        glow_radius=1.2,
        glow_passes=1,
    )
    rot = note_img.rotate(-90, expand=True)
    im.alpha_composite(rot, (1234, 408))
    return im


def render_tips_base(orig: Image.Image) -> Image.Image:
    im = orig.copy().convert("RGBA")
    arr = np.array(im)
    bg = tuple(int(v) for v in arr[400, 300])
    arr[526:572, 74:440] = bg
    im = Image.fromarray(arr, mode="RGBA")
    draw_glow_text(
        im,
        (80, 529),
        "TIPS Display Settings",
        load_font(FONT_MED, 22),
        (255, 255, 255, 255),
        (70, 105, 215, 220),
        glow_radius=1.8,
        glow_passes=2,
    )
    ImageDraw.Draw(im).text(
        (82, 554),
        "Choose how TIPS are displayed during gameplay.",
        font=load_font(FONT_FIRA, 13),
        fill=(235, 240, 248, 255),
    )
    return im


def render_favorite_base(orig: Image.Image) -> Image.Image:
    im = orig.copy().convert("RGBA")
    arr = np.array(im)
    bg = tuple(int(v) for v in arr[400, 300])
    arr[622:648, 792:945] = bg
    im = Image.fromarray(arr, mode="RGBA")
    draw_glow_text(
        im,
        (802, 626),
        "Confirm Dialog",
        load_font(FONT_MED, 17),
        (255, 255, 255, 255),
        (70, 105, 215, 200),
        glow_radius=1.2,
        glow_passes=1,
    )
    return im


def render_title_button(orig: Image.Image, is_unlock: bool = False) -> Image.Image:
    """Keep Row 0 (normal English) and Row 3 (disabled English) untouched, and synthesize
    Rows 1 & 2 (hover & active) directly from Row 0's exact English typography with Softpal's
    vibrant cyan glow — replacing the Japanese hover overlays with 100% native-looking English!
    """
    w, h = orig.size  # 346 x 244 (4 rows x 61px)
    sh = h // 4
    out = orig.copy().convert("RGBA")

    if is_unlock:
        # TITLE_BTN_UNLOCK has a custom blue/white crystal banner in all 4 rows.
        # Cleanly replace rows 1 & 2 text by taking Row 0's banner + white 'ALL UNLOCK'
        # and boosting cyan glow for hover/pressed states!
        row0 = orig.crop((0, 0, w, sh)).convert("RGBA")
        # Hover (row 1): slightly brighter cyan tint
        arr1 = np.array(row0, dtype=np.float32)
        arr1[:, :, 0] = np.clip(arr1[:, :, 0] * 0.90 + 10, 0, 255)
        arr1[:, :, 1] = np.clip(arr1[:, :, 1] * 1.15 + 28, 0, 255)
        arr1[:, :, 2] = np.clip(arr1[:, :, 2] * 1.20 + 35, 0, 255)
        row1 = Image.fromarray(arr1.astype(np.uint8), mode="RGBA")
        # Pressed (row 2): brighter highlight
        arr2 = np.array(row0, dtype=np.float32)
        arr2[:, :, 0] = np.clip(arr2[:, :, 0] * 1.10 + 25, 0, 255)
        arr2[:, :, 1] = np.clip(arr2[:, :, 1] * 1.22 + 40, 0, 255)
        arr2[:, :, 2] = np.clip(arr2[:, :, 2] * 1.25 + 45, 0, 255)
        row2 = Image.fromarray(arr2.astype(np.uint8), mode="RGBA")
        out.paste(row1, (0, sh))
        out.paste(row2, (0, sh * 2))
        return out

    # Standard transparent title menu buttons: Row 0 is pure crisp white English text!
    row0 = orig.crop((0, 0, w, sh)).convert("RGBA")
    alpha0 = row0.getchannel("A")

    # Build bright cyan glow halo from Row 0's alpha mask
    glow_src = Image.new("RGBA", (w, sh), (0, 235, 255, 0))
    glow_src.putalpha(alpha0)
    glow_blur = glow_src.filter(ImageFilter.GaussianBlur(radius=4.0))
    glow_tight = glow_src.filter(ImageFilter.GaussianBlur(radius=1.5))

    # Row 1 (Hover): cyan glow + crisp white/ice-cyan English text
    row1 = Image.new("RGBA", (w, sh), (0, 0, 0, 0))
    row1.alpha_composite(glow_blur)
    row1.alpha_composite(glow_blur)
    row1.alpha_composite(glow_tight)
    row1.alpha_composite(row0)

    # Row 2 (Pressed/Selected): slightly stronger glow + pure white core
    row2 = Image.new("RGBA", (w, sh), (0, 0, 0, 0))
    row2.alpha_composite(glow_blur)
    row2.alpha_composite(glow_blur)
    row2.alpha_composite(glow_blur)
    row2.alpha_composite(glow_tight)
    row2.alpha_composite(row0)

    # Clear rows 1 & 2 and paste synthesized glowing English
    blank_band = Image.new("RGBA", (w, sh * 2), (0, 0, 0, 0))
    out.paste(blank_band, (0, sh))
    out.paste(row1, (0, sh))
    out.paste(row2, (0, sh * 2))
    return out


def main() -> int:
    OUT_PGD.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    entries = read_pac2_index(SYSTEM_PAC)
    ent_map = {e.name.upper(): e for e in entries}

    def load_pgd(name: str) -> tuple[Image.Image, PgdMeta]:
        e = ent_map[name.upper()]
        with SYSTEM_PAC.open("rb") as f:
            f.seek(e.offset)
            return decode_pgd(f.read(e.size))

    saved_count = 0
    preview_set = {
        "POP_STRING.PGD",
        "POP_YES.PGD",
        "POP_UNLOCK.PGD",
        "COM_BTN_EXIT.PGD",
        "COM_BTN_EXIT_SA.PGD",
        "SYS_BASE.PGD",
        "SOUND_BASE.PGD",
        "SAVE_BASE.PGD",
        "LOAD_BASE.PGD",
        "TIPS_BASE.PGD",
        "FAVORITE_BASE.PGD",
        "TITLE_BTN_START.PGD",
        "TITLE_BTN_UNLOCK.PGD",
        "SOUND_UNIT_OTHER.PGD",
        "LOAD_BTN_LOCK.PGD",
        "SYS_BTN_WINDOW_ON.PGD",
        "TIPS_S_NO.PGD",
        "TIPS_S_ONMOUSE.PGD",
    }

    def save_override(name: str, im: Image.Image, meta: PgdMeta) -> None:
        nonlocal saved_count
        uname = name.upper()
        (OUT_PGD / uname).write_bytes(encode_pgd(im, meta))
        if uname in preview_set:
            im.save(PREVIEW_DIR / f"en_ui_{uname[:-4]}.png")
        saved_count += 1

    # 1. Popups
    im, meta = load_pgd("POP_STRING.PGD")
    save_override("POP_STRING.PGD", render_pop_string(im), meta)

    im, meta = load_pgd("POP_UNLOCK.PGD")
    save_override("POP_UNLOCK.PGD", render_pop_unlock(im), meta)

    for nm, label in [("POP_YES.PGD", "Yes"), ("POP_NO.PGD", "No")]:
        im, meta = load_pgd(nm)
        out = render_multistate_button(im, 3, [label], margin_x=10, margin_y=5, max_size=22)
        save_override(nm, out, meta)

    # 2. Common Navigation Pill Buttons (3 states each)
    com_specs = [
        ("COM_BTN_EXIT.PGD", ["Return"], "blue"),
        ("COM_BTN_EXIT_EX.PGD", ["Back"], "blue"),
        ("COM_BTN_EXIT_LO.PGD", ["Return"], "blue"),
        ("COM_BTN_EXIT_SA.PGD", ["Return"], "pink"),
        ("COM_BTN_GAMEEND.PGD", ["Quit"], "blue"),
        ("COM_BTN_GAMEEND_LO.PGD", ["Quit"], "blue"),
        ("COM_BTN_GAMEEND_SA.PGD", ["Quit"], "pink"),
        ("COM_BTN_TITLE.PGD", ["Title"], "blue"),
        ("COM_BTN_TITLE_LO.PGD", ["Title"], "blue"),
        ("COM_BTN_TITLE_SA.PGD", ["Title"], "pink"),
        ("COM_BTN_RESET.PGD", ["Reset Defaults"], "blue"),
        ("COM_BTN_RESET_LO.PGD", ["Reset Defaults"], "blue"),
        ("COM_BTN_RESET_SA.PGD", ["Reset Defaults"], "pink"),
        ("COM_BTN_WINDOW_RESTORE.PGD", ["Reset Size"], "blue"),
    ]
    for nm, lines, style in com_specs:
        im, meta = load_pgd(nm)
        out = render_multistate_button(im, 3, lines, style=style, margin_x=12, margin_y=5, max_size=21)
        save_override(nm, out, meta)

    # 3. System Config Screen + Toggles + Shortcut Menu
    im, meta = load_pgd("SYS_BASE.PGD")
    save_override("SYS_BASE.PGD", render_sys_base(im), meta)

    im, meta = load_pgd("SYS_TITLE_SCREENMODE.PGD")
    save_override("SYS_TITLE_SCREENMODE.PGD", render_sys_title_screenmode(im), meta)

    sys_toggles = [
        ("SYS_BTN_AUTO_ON.PGD", ["Yes"]),
        ("SYS_BTN_AUTO_OFF.PGD", ["No"]),
        ("SYS_BTN_SKIP_ON.PGD", ["Yes"]),
        ("SYS_BTN_SKIP_OFF.PGD", ["No"]),
        ("SYS_BTN_EFFECT_ON.PGD", ["On"]),
        ("SYS_BTN_EFFECT_OFF.PGD", ["Off"]),
        ("SYS_BTN_TSKIP_ON.PGD", ["All"]),
        ("SYS_BTN_TSKIP_OFF.PGD", ["Read Only"]),
        ("SYS_BTN_WINDOW_ON.PGD", ["Fullscreen"]),
        ("SYS_BTN_WINDOW_OFF.PGD", ["Window"]),
        ("SYS_BTN_CURSOR_05.PGD", ["5s"]),
        ("SYS_BTN_CURSOR_10.PGD", ["10s"]),
        ("SYS_BTN_CURSOR_20.PGD", ["20s"]),
        ("SYS_BTN_CURSOR_OFF.PGD", ["Off"]),
        ("SYS_BTN_FONT00.PGD", ["Gothic"]),
        ("SYS_BTN_FONT01.PGD", ["Mincho"]),
        ("SYS_BTN_FONT02.PGD", ["Default"]),
    ]
    for nm, lines in sys_toggles:
        im, meta = load_pgd(nm)
        mx = 6 if im.size[0] <= 100 else 10
        out = render_multistate_button(im, 4, lines, style="blue", margin_x=mx, margin_y=5, max_size=19)
        save_override(nm, out, meta)

    scut_labels = [
        "System",
        "Save",
        "Load",
        "Quick Save",
        "Quick Load",
        "Skip",
        "Auto Play",
        "Backlog",
        "Hide Text",
        "Replay Voice",
        "Resize Window",
        "None",
    ]
    for idx, lbl in enumerate(scut_labels):
        nm = f"SYS_SCUT_MENU{idx:02d}.PGD"
        im, meta = load_pgd(nm)
        # 4 rows x 30px, left-aligned text in Softpal dropdowns
        arr = np.array(im.convert("RGBA"))
        sh = im.size[1] // 4
        bgs = []
        for r in range(4):
            y0, y1 = r * sh, (r + 1) * sh
            bg = tuple(int(round(v)) for v in np.median(arr[y0 + 3 : y1 - 3, 152:168].reshape(-1, 4), axis=0))
            bgs.append(bg)
            arr[y0 + 2 : y1 - 2, 4:168] = bg
        out = Image.fromarray(arr, mode="RGBA")
        draw = ImageDraw.Draw(out)
        f = fit_font(draw, [lbl], FONT_MED, max_w=156, max_size=18, min_size=12)
        for r in range(4):
            y0, y1 = r * sh, (r + 1) * sh
            col = pick_text_color_for_bg(bgs[r], style="blue")
            bb = draw.textbbox((0, 0), lbl, font=f)
            ty = int(round(y0 + (sh - (bb[3] - bb[1])) / 2.0 - bb[1]))
            draw.text((10, ty), lbl, font=f, fill=col)
        save_override(nm, out, meta)

    # 4. Sound Config Screen + SOUND_UNIT*
    im, meta = load_pgd("SOUND_BASE.PGD")
    save_override("SOUND_BASE.PGD", render_sound_base(im), meta)

    for idx in range(11):
        nm = f"SOUND_UNIT{idx:02d}.PGD"
        im, meta = load_pgd(nm)
        save_override(nm, render_sound_unit(im, is_other=False), meta)
    im, meta = load_pgd("SOUND_UNIT_OTHER.PGD")
    save_override("SOUND_UNIT_OTHER.PGD", render_sound_unit(im, is_other=True), meta)

    # 5. Save & Load Screens + Action Buttons
    im, meta = load_pgd("SAVE_BASE.PGD")
    save_override("SAVE_BASE.PGD", render_save_or_load_base(im, is_save=True), meta)
    im, meta = load_pgd("LOAD_BASE.PGD")
    save_override("LOAD_BASE.PGD", render_save_or_load_base(im, is_save=False), meta)

    for pref, style in [("SAVE_BTN_", "pink"), ("LOAD_BTN_", "blue")]:
        for suf, lbl in [("COPY", "Copy Data"), ("DELETE", "Delete Data"), ("MOVE", "Move Data")]:
            nm = f"{pref}{suf}.PGD"
            im, meta = load_pgd(nm)
            out = render_multistate_button(im, 4, [lbl], style=style, margin_x=10, margin_y=4, max_size=19)
            save_override(nm, out, meta)
        # LOCK button: 301x162, 6 states x 27px, lock icon occupies x=0..92, text is x=95..296
        nm = f"{pref}LOCK.PGD"
        im, meta = load_pgd(nm)
        per_st = [["Lock Data"], ["Lock Data"], ["Data Locked"], ["Data Locked"], ["Unlock Data"], ["Unlock Data"]]
        out = render_multistate_button(
            im,
            6,
            ["Lock Data"],
            style=style,
            max_size=17,
            min_size=12,
            per_state_lines=per_st,
            x_offset_box=(95, 296),
        )
        save_override(nm, out, meta)

    # 6. TIPS Screen + Display Setting Buttons + NEW Tabs
    im, meta = load_pgd("TIPS_BASE.PGD")
    save_override("TIPS_BASE.PGD", render_tips_base(im), meta)

    tips_btn_specs = [
        ("TIPS_S_JIDOU.PGD", ["Auto-show TIPS", "window in-game"]),
        ("TIPS_S_NO.PGD", ["Show nothing"]),
        ("TIPS_S_ONMOUSE.PGD", ["Show on hover", "over term in text"]),
        ("TIPS_S_TUUTI.PGD", ["Notification only", "(no popup window)"]),
    ]
    for nm, lines in tips_btn_specs:
        im, meta = load_pgd(nm)
        out = render_multistate_button(im, 4, lines, style="blue", margin_x=10, margin_y=4, max_size=16, min_size=11)
        save_override(nm, out, meta)

    # TIPS_I00 (45x135, 3 states) & TIPS_T00 (345x36, 1 state): 新 -> NEW
    im, meta = load_pgd("TIPS_I00.PGD")
    out = render_multistate_button(im, 3, ["NEW"], style="blue", margin_x=3, margin_y=3, max_size=18, min_size=12)
    save_override("TIPS_I00.PGD", out, meta)

    im, meta = load_pgd("TIPS_T00.PGD")
    out = render_multistate_button(im, 1, ["NEW"], style="blue", margin_x=6, margin_y=3, max_size=20, min_size=14)
    save_override("TIPS_T00.PGD", out, meta)

    # 7. Favorite Voice & BGM Music Mode Screens
    im, meta = load_pgd("FAVORITE_BASE.PGD")
    save_override("FAVORITE_BASE.PGD", render_favorite_base(im), meta)

    fav_bgm_specs = [
        ("FAV_BTN_1DEL.PGD", ["Delete", "Selected"], 4, 15),
        ("FAV_BTN_1DOWN.PGD", ["Move", "Down 1"], 4, 15),
        ("FAV_BTN_1UP.PGD", ["Move", "Up 1"], 4, 15),
        ("FAV_BTN_TOP.PGD", ["Move to", "Top"], 4, 15),
        ("FAV_BTN_BOTTOM.PGD", ["Move to", "Bottom"], 4, 15),
        ("FAV_BTN_ALLDEL.PGD", ["Delete All", "Checked Voices"], 4, 16),
        ("FAV_BTN_ALLOFF.PGD", ["Uncheck All", "Boxes"], 4, 16),
        ("FAV_BTN_ALLON.PGD", ["Check All", "Boxes"], 4, 16),
        ("FAV_BTN_ALLPLAY.PGD", ["Play All", "Checked Voices"], 4, 16),
        ("BGM_BTN_ALL.PGD", ["Play Playlist", "Continuously"], 4, 15),
        ("BGM_BTN_NORMAL.PGD", ["Normal Playback"], 4, 16),
        ("BGM_BTN_SHUFFLE.PGD", ["Shuffle Playlist"], 4, 16),
        ("BGM_BTN_RESET.PGD", ["Reset", "Order"], 4, 15),
        ("BGM_BTN_TOP.PGD", ["Move to", "Top"], 4, 15),
        ("BGM_BTN_UP.PGD", ["Move", "Up 1"], 4, 15),
        ("BGM_BTN_DOWN.PGD", ["Move", "Down 1"], 4, 15),
        ("BGM_BTN_BOTTOM.PGD", ["Move to", "Bottom"], 4, 15),
    ]
    for nm, lines, n_st, msz in fav_bgm_specs:
        im, meta = load_pgd(nm)
        mx = 6 if im.size[0] <= 130 else 10
        out = render_multistate_button(im, n_st, lines, style="blue", margin_x=mx, margin_y=4, max_size=msz, min_size=10)
        save_override(nm, out, meta)

    # 8. Title Screen Hover/Active States (14 buttons)
    title_btns = [
        "TITLE_BTN_START.PGD",
        "TITLE_BTN_CONTINUE.PGD",
        "TITLE_BTN_LOAD.PGD",
        "TITLE_BTN_SYSTEM.PGD",
        "TITLE_BTN_EXTRA.PGD",
        "TITLE_BTN_END.PGD",
        "TITLE_BTN_BGM.PGD",
        "TITLE_BTN_CGM.PGD",
        "TITLE_BTN_SCENE.PGD",
        "TITLE_BTN_TIPS.PGD",
        "TITLE_BTN_VOICE.PGD",
        "TITLE_BTN_RETURN.PGD",
        "TITLE_BTN_SPECIAL.PGD",
        "TITLE_BTN_UNLOCK.PGD",
    ]
    for nm in title_btns:
        im, meta = load_pgd(nm)
        out = render_title_button(im, is_unlock=(nm == "TITLE_BTN_UNLOCK.PGD"))
        save_override(nm, out, meta)

    print(f"Rendered and encoded {saved_count} localized UI .PGD files into {OUT_PGD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
