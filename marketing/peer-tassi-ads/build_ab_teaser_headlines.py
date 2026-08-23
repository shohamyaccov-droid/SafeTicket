"""A/B headline variations on the original TradeTix waitlist teaser (4:5)."""
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
SQUEEZE = 0.76
MAX_W = 1020
CYAN = (90, 204, 226)
WHITE = (252, 252, 253)

# Original headline stack: two large white lines + one cyan payoff.
Y1, Y2, Y3 = 122, 224, 348


def he(text: str) -> str:
    return get_display(arabic_reshaper.reshape(text))


def heebo(size: int, weight: float = 900) -> ImageFont.FreeTypeFont:
    fnt = ImageFont.truetype(str(FONT_PATH), size)
    fnt.set_variation_by_axes([weight])
    return fnt


def wipe_band(im: Image.Image, y0: int = 118, y1: int = 396) -> Image.Image:
    arr = np.array(im)
    tex = arr[92:118]
    reps = int(np.ceil((y1 - y0) / tex.shape[0]))
    arr[y0:y1] = np.tile(tex, (reps, 1, 1))[: y1 - y0]
    return Image.fromarray(arr)


def _bbox(visual: str, fnt: ImageFont.FreeTypeFont):
    d = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    return d.textbbox((0, 0), visual, font=fnt)


def render_line(
    text: str,
    size: int,
    fill: tuple[int, int, int],
    squeeze: float | None,
    latin: str = "",
) -> Image.Image:
    fnt = heebo(size * SCALE)
    visual = he(text)
    bb = _bbox(visual, fnt)
    pad = 10 * SCALE
    he_w, he_h = bb[2] - bb[0], bb[3] - bb[1]
    lat_w = lat_h = 0
    lbb = (0, 0, 0, 0)
    if latin:
        lbb = _bbox(latin, fnt)
        lat_w, lat_h = lbb[2] - lbb[0], lbb[3] - lbb[1]
    gap = (12 * SCALE) if latin else 0
    tw = he_w + lat_w + gap + pad * 2
    th = max(he_h, lat_h) + pad * 2
    layer = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # LTR paste: latin on the left, Hebrew on the right (correct RTL reading).
    x = pad
    if latin:
        d.text((x - lbb[0], pad - lbb[1] + (he_h - lat_h) // 2), latin, font=fnt, fill=fill)
        x += lat_w + gap
    d.text((x - bb[0], pad - bb[1]), visual, font=fnt, fill=fill)
    if squeeze and squeeze != 1:
        layer = layer.resize(
            (max(1, int(layer.width * squeeze)), layer.height), Image.Resampling.LANCZOS
        )
    layer = layer.resize(
        (max(1, layer.width // SCALE), max(1, layer.height // SCALE)),
        Image.Resampling.LANCZOS,
    )
    if fill[0] > 200:
        arr = np.array(layer)
        alpha = arr[:, :, 3]
        noise = np.random.default_rng(4).integers(-22, 23, alpha.shape, dtype=np.int16)
        for c in range(3):
            ch = arr[:, :, c].astype(np.int16)
            arr[:, :, c] = np.where(alpha > 0, np.clip(ch + noise, 0, 255), ch).astype(np.uint8)
        layer = Image.fromarray(arr)
    return layer


def fit_line(
    text: str,
    size: int,
    fill: tuple[int, int, int],
    squeeze: float | None,
    latin: str = "",
    min_w: int = 0,
    max_size: int = 112,
) -> Image.Image:
    try_size = size
    img = render_line(text, try_size, fill, squeeze, latin)
    while min_w and img.width < min_w and try_size < max_size:
        try_size += 2
        img = render_line(text, try_size, fill, squeeze, latin)
    while img.width > MAX_W and try_size > 28:
        try_size -= 2
        img = render_line(text, try_size, fill, squeeze, latin)
    return img


def paste_centered(im: Image.Image, line: Image.Image, y: int) -> None:
    im.paste(line, ((W - line.width) // 2, y), line)


def compose(src: Image.Image, white1: str, white2: str, cyan: str, cyan_latin: str = "") -> Image.Image:
    im = wipe_band(src.copy())
    l1 = fit_line(white1, 88, WHITE, SQUEEZE, min_w=780)
    l2 = fit_line(white2, 80, WHITE, SQUEEZE, min_w=720)
    l3 = fit_line(cyan, 42, CYAN, None, latin=cyan_latin, min_w=640, max_size=46)
    y = 120
    paste_centered(im, l1, y)
    y = y + l1.height + 10
    paste_centered(im, l2, y)
    y = min(max(348, y + l2.height + 16), 396 - l3.height)
    paste_centered(im, l3, y)
    return im


VARIANTS = [
    {
        "name": "tradetix-ab-v1-cant-go-4x5.png",
        "white1": "קניתם כרטיס להופעה",
        "white2": "ואתם לא יכולים ללכת?",
        "cyan": "הקונים כבר מחכים לו ברשימת ההמתנה שלנו.",
        "latin": "",
    },
    {
        "name": "tradetix-ab-v2-stuck-ticket-4x5.png",
        "white1": "נתקעתם עם כרטיס",
        "white2": "שקניתם להופעה?",
        "cyan": "הקונים כבר מחכים לו ברשימת ההמתנה ב-",
        "latin": "TradeTix.",
    },
    {
        "name": "tradetix-ab-v3-facebook-sellers-4x5.png",
        "white1": "מוכרים כרטיס בפייסבוק?",
        "white2": 'בלי "עוד רלוונטי"',
        "cyan": "יש קונים שמחכים ברשימת ההמתנה שלנו.",
        "latin": "",
    },
]


def main() -> None:
    if not SRC.exists():
        raise FileNotFoundError(SRC)
    if not FONT_PATH.exists():
        raise FileNotFoundError(FONT_PATH)
    src = Image.open(SRC).convert("RGB")
    for v in VARIANTS:
        out = compose(src, v["white1"], v["white2"], v["cyan"], v["latin"])
        path = OUT_DIR / v["name"]
        out.save(path, "PNG")
        print(f"saved {path} {out.size}")


if __name__ == "__main__":
    main()
