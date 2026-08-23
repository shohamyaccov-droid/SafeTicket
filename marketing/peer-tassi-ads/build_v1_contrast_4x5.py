"""Edit the original waitlist 3x4: replace כאן with ברשימת המתנה, export 4:5.

Does not rebuild the creative. Only the headline word and the Facebook 4:5 size.
"""
from __future__ import annotations

from pathlib import Path

import arabic_reshaper
import numpy as np
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(r"C:\Users\user\Desktop\SafeTicket\marketing\peer-tassi-ads")
SRC = OUT_DIR / "tradetix-waitlist-v1-contrast-3x4.png"
TARGET_W, TARGET_H = 1080, 1350  # Facebook mobile feed 4:5
FONT_BOLD = r"C:\Windows\Fonts\arialbd.ttf"

HEADLINE = "הקונה של הכרטיס שלך כבר ברשימת המתנה."
SUBLINE = "רק נשאר להעלות אותו."
MAX_TEXT_W = 960  # keep a small side margin so Facebook will not cut letters

# Original headline sits in this band (do not touch phones / footer).
HEAD_Y0, HEAD_Y1 = 88, 180
LINE1_BAND = (100, 138)
LINE2_BAND = (142, 168)


def he(text: str) -> str:
    return get_display(arabic_reshaper.reshape(text))


def cover_headline(im: Image.Image) -> Image.Image:
    """Stamp nearby texture over the old headline so the rest of the ad is untouched."""
    arr = np.array(im)
    above = arr[68:88]
    band_h = HEAD_Y1 - HEAD_Y0
    reps = int(np.ceil(band_h / above.shape[0]))
    fill = np.tile(above, (reps, 1, 1))[:band_h]
    arr[HEAD_Y0:HEAD_Y1] = fill
    return Image.fromarray(arr)


def fit_font(draw: ImageDraw.ImageDraw, text: str, start: int) -> ImageFont.FreeTypeFont:
    visual = he(text)
    size = start
    while size >= 28:
        font = ImageFont.truetype(FONT_BOLD, size)
        bb = draw.textbbox((0, 0), visual, font=font)
        if bb[2] - bb[0] <= MAX_TEXT_W:
            return font
        size -= 1
    return ImageFont.truetype(FONT_BOLD, 28)


def draw_in_band(
    draw: ImageDraw.ImageDraw,
    text: str,
    y0: int,
    y1: int,
    font: ImageFont.FreeTypeFont,
    w: int,
) -> None:
    visual = he(text)
    bb = draw.textbbox((0, 0), visual, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x = (w - tw) // 2 - bb[0]
    y = y0 + (y1 - y0 - th) // 2 - bb[1]
    draw.text((x + 1, y + 1), visual, font=font, fill=(0, 0, 0))
    draw.text((x, y), visual, font=font, fill=(255, 255, 255))


def replace_headline(im: Image.Image) -> Image.Image:
    im = cover_headline(im.convert("RGB"))
    d = ImageDraw.Draw(im)
    font1 = fit_font(d, HEADLINE, 48)
    font2 = ImageFont.truetype(FONT_BOLD, 34)
    draw_in_band(d, HEADLINE, *LINE1_BAND, font1, im.width)
    draw_in_band(d, SUBLINE, *LINE2_BAND, font2, im.width)
    return im


def pad_to_4x5(im: Image.Image) -> Image.Image:
    """Keep the whole design visible: extend the red/green sides, then scale to 1080x1350."""
    arr = np.array(im)
    h, w, _ = arr.shape
    left_c = tuple(int(v) for v in arr[h // 2, 6:24].mean(axis=0))
    right_c = tuple(int(v) for v in arr[h // 2, w - 24 : w - 6].mean(axis=0))
    target_w = int(round(h * 4 / 5))
    pad = max(0, target_w - w)
    left_pad, right_pad = pad // 2, pad - pad // 2
    canvas = Image.new("RGB", (target_w, h))
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, left_pad + w // 2, h], fill=left_c)
    d.rectangle([left_pad + w // 2, 0, target_w, h], fill=right_c)
    canvas.paste(im, (left_pad, 0))
    return canvas.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)


def main() -> None:
    if not SRC.exists():
        raise FileNotFoundError(SRC)
    edited = replace_headline(Image.open(SRC))
    out_3x4 = OUT_DIR / "tradetix-waitlist-v1-contrast-3x4.png"
    out_4x5 = OUT_DIR / "tradetix-waitlist-v1-contrast-4x5.png"
    out_fb = OUT_DIR / "tradetix-waitlist-v1-contrast-facebook-4x5.png"
    edited.save(out_3x4, "PNG", optimize=True)
    final = pad_to_4x5(edited)
    final.save(out_4x5, "PNG", optimize=True)
    final.save(out_fb, "PNG", optimize=True)
    print(f"saved {out_3x4} {edited.size}")
    print(f"saved {out_4x5} {final.size}")
    print(f"saved {out_fb} {final.size}")


if __name__ == "__main__":
    main()
