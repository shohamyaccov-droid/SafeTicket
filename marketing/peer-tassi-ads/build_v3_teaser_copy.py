"""Change teaser copy while keeping the original headline look.

Unchanged lines stay as original pixels. New lines are Heebo Black,
horizontally condensed to match the original display type.
"""
from __future__ import annotations

from pathlib import Path

import arabic_reshaper
import numpy as np
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(r"C:\Users\user\Desktop\SafeTicket\marketing\peer-tassi-ads")
SRC = OUT_DIR / "tradetix-waitlist-v3-teaser-story-4x5-original.png"
FONT_PATH = OUT_DIR / "fonts" / "Heebo-variable.ttf"

W, H = 1080, 1350
SCALE = 4
SQUEEZE = 0.76  # original headlines are condensed vs regular Heebo
CYAN = (90, 204, 226)
WHITE = (252, 252, 253)


def he(text: str) -> str:
    return get_display(arabic_reshaper.reshape(text))


def heebo(size: int, weight: float = 900) -> ImageFont.FreeTypeFont:
    fnt = ImageFont.truetype(str(FONT_PATH), size)
    fnt.set_variation_by_axes([weight])
    return fnt


def wipe_band(im: Image.Image, y0: int, y1: int) -> Image.Image:
    """Cover a text band with the original black texture from above the headlines."""
    arr = np.array(im)
    tex = arr[92:118]
    reps = int(np.ceil((y1 - y0) / tex.shape[0]))
    fill = np.tile(tex, (reps, 1, 1))[: y1 - y0]
    arr[y0:y1] = fill
    return Image.fromarray(arr)


def render_line(text: str, size: int, fill: tuple[int, int, int], squeeze: float | None) -> Image.Image:
    fnt = heebo(size * SCALE)
    visual = he(text)
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    bb = probe.textbbox((0, 0), visual, font=fnt)
    pad = 8 * SCALE
    tw, th = bb[2] - bb[0] + pad * 2, bb[3] - bb[1] + pad * 2
    layer = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((pad - bb[0], pad - bb[1]), visual, font=fnt, fill=fill)
    if squeeze and squeeze != 1:
        layer = layer.resize((max(1, int(layer.width * squeeze)), layer.height), Image.Resampling.LANCZOS)
    layer = layer.resize((max(1, layer.width // SCALE), max(1, layer.height // SCALE)), Image.Resampling.LANCZOS)
    if fill[0] > 200:
        arr = np.array(layer)
        alpha = arr[:, :, 3]
        noise = np.random.default_rng(4).integers(-24, 25, alpha.shape, dtype=np.int16)
        for c in range(3):
            ch = arr[:, :, c].astype(np.int16)
            arr[:, :, c] = np.where(alpha > 0, np.clip(ch + noise, 0, 255), ch).astype(np.uint8)
        layer = Image.fromarray(arr)
    return layer


def paste_centered(im: Image.Image, line: Image.Image, y: int) -> None:
    x = (W - line.width) // 2
    im.paste(line, (x, y), line)


def version_concert_ticket(src: Image.Image) -> Image.Image:
    # Keep original line 2, cyan, phone, CTA. Only swap the first headline.
    im = wipe_band(src.copy(), 118, 224)
    line = render_line("הכרטיס להופעה שלך כבר נמכר.", 96, WHITE, SQUEEZE)
    paste_centered(im, line, 127 + max(0, (90 - line.height) // 2))
    return im


def version_stuck_hook(src: Image.Image) -> Image.Image:
    im = wipe_band(src.copy(), 118, 396)
    paste_centered(im, render_line("תקועים עם כרטיס להופעה?", 96, WHITE, SQUEEZE), 122)
    paste_centered(im, render_line("הקונים כבר מחכים לו עכשיו", 80, WHITE, SQUEEZE), 226)
    paste_centered(
        im,
        render_line("ברשימת ההמתנה ב-TradeTix.", 40, CYAN, None),
        348,
    )
    return im


def main() -> None:
    if not SRC.exists():
        raise FileNotFoundError(SRC)
    if not FONT_PATH.exists():
        raise FileNotFoundError(FONT_PATH)
    src = Image.open(SRC).convert("RGB")
    a = version_concert_ticket(src)
    b = version_stuck_hook(src)
    out_a = OUT_DIR / "tradetix-waitlist-v3-teaser-story-4x5.png"
    out_b = OUT_DIR / "tradetix-waitlist-v3-teaser-stuck-4x5.png"
    a.save(out_a, "PNG")
    b.save(out_b, "PNG")
    print(f"saved {out_a} {a.size}")
    print(f"saved {out_b} {b.size}")


if __name__ == "__main__":
    main()
