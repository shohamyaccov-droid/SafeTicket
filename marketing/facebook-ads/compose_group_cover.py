"""Facebook group cover: TradeTix brand + short Hebrew rules, mobile-safe center."""

from __future__ import annotations

from pathlib import Path

from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
FONTS = ROOT / "fonts"
OUT_DIR = ROOT
DESKTOP = Path(r"C:\Users\user\Desktop\TradeTix-ads")

BG = ROOT / "tradetix-group-cover-bg.png"
F_EX = "Gstatic-Assistant-ExtraBold.ttf"
F_BD = "Gstatic-Assistant-Bold.ttf"
F_SM = "Gstatic-Assistant-SemiBold.ttf"

# Official Facebook group cover
W, H = 1640, 856
CYAN = (70, 240, 255, 255)
WHITE = (255, 255, 255, 255)
MUTED = (210, 225, 232, 255)
STROKE = (0, 8, 16, 210)


def rtl(t: str) -> str:
    return get_display(t)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def tw(fnt, t: str) -> tuple[int, int]:
    b = fnt.getbbox(t)
    return b[2] - b[0], b[3] - b[1]


def cover_resize(im: Image.Image, size: tuple[int, int], top_bias: float = 0.22) -> Image.Image:
    tw_, th = size
    scale = max(tw_ / im.width, th / im.height)
    nw, nh = int(im.width * scale), int(im.height * scale)
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - tw_) // 2
    extra = nh - th
    top = int(extra * top_bias)
    return im.crop((left, top, left + tw_, top + th))


def darken_center(size: tuple[int, int]) -> Image.Image:
    """Soft black scrim so type stays readable after Facebook crops the sides."""
    ov = Image.new("RGBA", size, (0, 0, 0, 0))
    px = ov.load()
    w, h = size
    cx, cy = w / 2, h * 0.62
    for y in range(h):
        for x in range(w):
            dx = abs(x - cx) / (w * 0.38)
            dy = abs(y - cy) / (h * 0.42)
            r = (dx * dx + dy * dy) ** 0.5
            a = int(max(0, min(1, 1.15 - r)) * 175)
            if a:
                px[x, y] = (0, 0, 0, a)
    return ov.filter(ImageFilter.GaussianBlur(18))


def draw_centered(draw, text, y, fnt, fill, stroke_w=4):
    w, h = tw(fnt, text)
    draw.text(
        ((W - w) // 2, y),
        text,
        font=fnt,
        fill=fill,
        stroke_width=stroke_w,
        stroke_fill=STROKE,
    )
    return y + h


def pill(base: Image.Image, text: str, y: int, fnt, fill=CYAN) -> int:
    w, h = tw(fnt, text)
    pad_x, pad_y = 28, 10
    bw, bh = w + pad_x * 2, h + pad_y * 2
    x = (W - bw) // 2
    layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((0, 0, bw - 1, bh - 1), radius=bh // 2, fill=(0, 20, 28, 210), outline=fill, width=3)
    d.text((pad_x, pad_y - 2), text, font=fnt, fill=WHITE)
    glow = layer.filter(ImageFilter.GaussianBlur(6))
    base.alpha_composite(glow, (x, y))
    base.alpha_composite(layer, (x, y))
    return y + bh


def compose() -> Image.Image:
    bg = cover_resize(Image.open(BG).convert("RGB"), (W, H)).convert("RGBA")
    bg.alpha_composite(darken_center((W, H)))
    draw = ImageDraw.Draw(bg)

    # All type in the center column, finished before y≈590 so mobile crop keeps it.
    y = 348
    y = draw_centered(draw, "TRADETIX", y, font(F_EX, 36), CYAN, stroke_w=3) + 4
    y = draw_centered(draw, rtl("הקבוצה הבטוחה"), y, font(F_EX, 70), WHITE, stroke_w=5) + 0
    y = draw_centered(draw, rtl("לכרטיסים בישראל"), y, font(F_EX, 70), WHITE, stroke_w=5) + 4
    y = draw_centered(draw, rtl("הכסף בנאמנות עד הכניסה"), y, font(F_BD, 32), CYAN, stroke_w=3) + 16

    rule_f = font(F_EX, 26)
    y = pill(bg, rtl("0% עמלה למוכרים"), y, rule_f) + 8
    y = pill(bg, rtl("תשלום רק באתר  ·  לא בביט ישיר"), y, rule_f) + 10

    draw = ImageDraw.Draw(bg)
    y = draw_centered(draw, rtl("אין ספסרות  ·  עוקץ = הרחקה"), y, font(F_BD, 22), MUTED, stroke_w=2) + 4
    draw_centered(draw, "tradetix.co.il", y, font(F_SM, 22), MUTED, stroke_w=2)
    return bg.convert("RGB")


def mobile_preview(cover: Image.Image) -> Image.Image:
    """Simulate iPhone group header: full-width, short crop of the center."""
    phone_w, phone_h = 1170, 510  # 3x ~390x170
    # Facebook mobile often crops ~12% of each side + a little top.
    side = int(cover.width * 0.12)
    top = 70
    crop = cover.crop((side, top, cover.width - side, top + int((cover.width - 2 * side) * phone_h / phone_w)))
    return crop.resize((phone_w, phone_h), Image.Resampling.LANCZOS)


def main() -> None:
    DESKTOP.mkdir(parents=True, exist_ok=True)
    cover = compose()
    phone = mobile_preview(cover)
    for dest in (OUT_DIR, DESKTOP):
        cover.save(dest / "tradetix-facebook-group-cover.png", "PNG", optimize=True)
        phone.save(dest / "tradetix-facebook-group-cover-mobile-preview.png", "PNG", optimize=True)
    print("wrote", W, "x", H)


if __name__ == "__main__":
    main()
