"""The pack icon (pack.png): a rounded square of white paper with あ in black brush ink for the kana-only language,
over a band of the grade colors (1 red ... 6 brown) with 一〜六 in white for the six grade languages. The font is a
brush font, Yuji Syuku (SIL OFL 1.1); only the drawn image is kept. Drawn at 512 and shrunk to 128."""
import io

from PIL import Image, ImageDraw, ImageFont

GRADE_COLORS = {1: "#e53935", 2: "#fb8c00", 3: "#43a047", 4: "#1e88e5", 5: "#8e24aa", 6: "#6d4c41"}
PAPER = "#ffffff"
INK = "#1a1a1a"
SIZE = 512
OUT_SIZE = 128
S = SIZE / 64  # the layout is in units of a 64 x 64 icon
SQUARE = (2 * S, 2 * S, 61 * S, 61 * S)


def centered(draw, font_path, c, center, box, color):
    """Draw c in color, as large as fits in a box x box square around center."""
    size = int(box)
    while True:
        font = ImageFont.truetype(font_path, size)
        left, top, right, bottom = draw.textbbox((0, 0), c, font=font)
        if right - left <= box and bottom - top <= box:
            break
        size -= 4
    draw.text((center[0] - (left + right) / 2, center[1] - (top + bottom) / 2), c, font=font, fill=color)


def icon(font_path):
    background = Image.new("RGBA", (SIZE, SIZE), PAPER)
    draw = ImageDraw.Draw(background)
    centered(draw, font_path, "あ", (SIZE / 2, 22 * S), 30 * S, INK)
    # The grade band, inside the straight part of the square so the corners do not cut it
    left, right, top, bottom = 6 * S, 57 * S, 40 * S, 52 * S
    cell = (right - left) / 6
    for g, color in GRADE_COLORS.items():
        x = left + (g - 1) * cell
        draw.rectangle((x, top, x + cell, bottom), fill=color)
        centered(draw, font_path, "一二三四五六"[g - 1], (x + cell / 2, (top + bottom) / 2), cell * 0.8, PAPER)
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(SQUARE, radius=12 * S, fill=255)
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    image.paste(background, mask=mask)
    ImageDraw.Draw(image).rounded_rectangle(SQUARE, radius=12 * S, outline="#212121", width=int(2 * S))
    return image.resize((OUT_SIZE, OUT_SIZE), Image.LANCZOS)


def icon_png(font_path: str) -> bytes:
    out = io.BytesIO()
    icon(font_path).save(out, format="PNG", optimize=True)
    return out.getvalue()
