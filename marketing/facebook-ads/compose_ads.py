"""Compose TradeTix Facebook ads: photoreal backgrounds + Assistant type (Ben Tzur look)."""

from __future__ import annotations

from pathlib import Path

from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
ASSETS = Path(r"C:\Users\user\.cursor\projects\c-Users-user-Desktop-SafeTicket\assets")
FONTS = ROOT / "fonts"
DESKTOP = Path(r"C:\Users\user\Desktop\TradeTix-ads")

W, H = 1080, 1350  # Facebook 4:5
MARGIN = 52

F_EXTRABOLD = "Gstatic-Assistant-ExtraBold.ttf"
F_BOLD = "Gstatic-Assistant-Bold.ttf"
F_SEMIBOLD = "Gstatic-Assistant-SemiBold.ttf"


def rtl(text: str) -> str:
    return get_display(text)


def load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def cover_resize(im: Image.Image, size: tuple[int, int], top_bias: float = 0.28) -> Image.Image:
    tw, th = size
    scale = max(tw / im.width, th / im.height)
    nw, nh = int(im.width * scale), int(im.height * scale)
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - tw) // 2
    extra_h = nh - th
    top = int(extra_h * top_bias)
    return im.crop((left, top, left + tw, top + th))


def vertical_fade(size: tuple[int, int], top: int, bottom: int) -> Image.Image:
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    px = overlay.load()
    w, h = size
    for y in range(top):
        a = int(160 * (1 - y / max(top, 1)))
        for x in range(w):
            px[x, y] = (0, 0, 0, a)
    for i in range(bottom):
        y = h - 1 - i
        a = int(190 * (1 - i / max(bottom, 1)))
        for x in range(w):
            px[x, y] = (0, 0, 0, a)
    return overlay


def rounded_rect(size, radius, fill, outline=None, outline_width=2) -> Image.Image:
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1),
        radius=radius,
        fill=fill,
        outline=outline,
        width=outline_width,
    )
    return im


def glow_layer(base: Image.Image, color, radius=18, alpha=160) -> Image.Image:
    padded = Image.new("RGBA", (base.width + radius * 4, base.height + radius * 4), (0, 0, 0, 0))
    a = base.split()[-1]
    glow = Image.new("RGBA", base.size, color + (alpha,))
    glow.putalpha(a)
    padded.paste(glow, (radius * 2, radius * 2), glow)
    return padded.filter(ImageFilter.GaussianBlur(radius))


def draw_lock(draw: ImageDraw.ImageDraw, cx: int, cy: int, s: int, color=(255, 255, 255, 255), stroke=2):
    """Simple padlock matching the Ben Tzur TradeTix mark."""
    body_w, body_h = int(s * 0.72), int(s * 0.52)
    bx = int(cx - body_w / 2)
    by = int(cy - s * 0.02)
    draw.rounded_rectangle((bx, by, bx + body_w, by + body_h), radius=max(2, s // 7), fill=color)
    sh_w = int(body_w * 0.58)
    sh_h = int(s * 0.55)
    sx0 = int(cx - sh_w / 2)
    sy0 = int(by - sh_h + stroke + 2)
    draw.arc((sx0, sy0, sx0 + sh_w, sy0 + sh_h), start=200, end=340, fill=color, width=stroke)


def draw_check_circle(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color=(255, 255, 255, 255), stroke=3):
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=stroke)
    p1 = (cx - r * 0.42, cy + r * 0.02)
    p2 = (cx - r * 0.08, cy + r * 0.38)
    p3 = (cx + r * 0.46, cy - r * 0.32)
    draw.line([p1, p2, p3], fill=color, width=stroke, joint="curve")


def text_size(font: ImageFont.FreeTypeFont, text: str) -> tuple[int, int]:
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def fit_font(name: str, text: str, max_width: int, start: int, min_size: int = 22) -> ImageFont.FreeTypeFont:
    size = start
    while size > min_size:
        font = load_font(name, size)
        w, _ = text_size(font, text)
        if w <= max_width:
            return font
        size -= 2
    return load_font(name, min_size)


def measure_tracked(font: ImageFont.FreeTypeFont, text: str, tracking: int) -> tuple[int, int]:
    if not text:
        return 0, 0
    widths = []
    height = 0
    for ch in text:
        w, h = text_size(font, ch)
        widths.append(w)
        height = max(height, h)
    total = sum(widths) + tracking * max(len(text) - 1, 0)
    return total, height


def draw_tracked(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, font, fill, tracking: int) -> None:
    for i, ch in enumerate(text):
        draw.text((x, y), ch, font=font, fill=fill)
        w, _ = text_size(font, ch)
        x += w + (tracking if i < len(text) - 1 else 0)


def render_display_line(
    text: str,
    font: ImageFont.FreeTypeFont,
    fill=(255, 255, 255, 255),
    glow: bool = True,
    tracking: int = 0,
    scale_x: float = 1.0,
) -> Image.Image:
    """Assistant ExtraBold, tight tracking, horizontally condensed like Ben Tzur."""
    w, h = measure_tracked(font, text, tracking)
    pad = 36
    layer = Image.new("RGBA", (max(w, 1) + pad * 2, h + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    draw_tracked(d, pad, pad, text, font, fill, tracking)

    if glow:
        alpha = layer.split()[-1]
        orange = Image.new("RGBA", layer.size, (255, 145, 55, 0))
        orange.putalpha(alpha.point(lambda p: int(p * 0.40)))
        white = Image.new("RGBA", layer.size, (255, 255, 255, 0))
        white.putalpha(alpha.point(lambda p: int(p * 0.30)))
        out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        out.alpha_composite(orange.filter(ImageFilter.GaussianBlur(9)))
        out.alpha_composite(white.filter(ImageFilter.GaussianBlur(3)))
        out.alpha_composite(layer)
        layer = out

    if abs(scale_x - 1.0) > 0.001:
        nw = max(1, int(layer.width * scale_x))
        layer = layer.resize((nw, layer.height), Image.Resampling.LANCZOS)
    return layer


def trim_transparent(im: Image.Image, pad: int = 8) -> Image.Image:
    alpha = im.split()[-1]
    bbox = alpha.getbbox()
    if not bbox:
        return im
    l, t, r, b = bbox
    l = max(0, l - pad)
    t = max(0, t - pad)
    r = min(im.width, r + pad)
    b = min(im.height, b + pad)
    return im.crop((l, t, r, b))


def paste_centered(canvas: Image.Image, layer: Image.Image, cy: int) -> int:
    layer = trim_transparent(layer, pad=6)
    x = (W - layer.width) // 2
    y = cy - layer.height // 2
    canvas.alpha_composite(layer, (x, y))
    return y + layer.height


def overlay_typeplate(canvas: Image.Image, plate_path: Path, y: int = 72, max_w: int = 980, max_h: int = 250) -> int:
    """Screen-blend a black-bg Ben Tzur-style title plate onto the ad."""
    import numpy as np

    plate = Image.open(plate_path).convert("RGB")
    arr = np.array(plate)
    luma = arr.max(axis=2)
    ys, xs = np.where(luma > 22)
    plate = plate.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    scale = min(max_w / plate.width, max_h / plate.height)
    nw, nh = max(1, int(plate.width * scale)), max(1, int(plate.height * scale))
    plate = plate.resize((nw, nh), Image.Resampling.LANCZOS)
    x = (W - nw) // 2

    base = canvas.convert("RGB")
    base_np = np.array(base, dtype=np.float32) / 255.0
    overlay = np.zeros_like(base_np)
    overlay[y : y + nh, x : x + nw] = np.array(plate, dtype=np.float32) / 255.0
    blended = 1.0 - (1.0 - base_np) * (1.0 - overlay)
    rgb = Image.fromarray((blended * 255).clip(0, 255).astype("uint8"))
    if canvas.mode == "RGBA":
        out = rgb.convert("RGBA")
        out.putalpha(canvas.split()[-1])
        return out, y + nh
    return rgb, y + nh


def compose(bg_path: Path, out_path: Path, spec: dict) -> None:
    spec = dict(spec)
    for key in ("title", "subtitle", "badge", "trust_right", "trust_join", "cta_he"):
        spec[key] = rtl(spec[key])
    if spec.get("trust_left"):
        spec["trust_left"] = rtl(spec["trust_left"])

    bg = cover_resize(Image.open(bg_path).convert("RGB"), (W, H), top_bias=0.22)
    canvas = bg.convert("RGBA")
    canvas.alpha_composite(vertical_fade((W, H), top=400, bottom=400))

    ui = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ui)

    # --- Logo top-left (small, like Ben Tzur) ---
    logo_font = load_font(F_BOLD, 30)
    logo = "TradeTix"
    draw.text((MARGIN, 40), logo, font=logo_font, fill=(255, 255, 255, 255))
    lw, lh = text_size(logo_font, logo)
    lock_cx = MARGIN + lw + 26
    lock_cy = 40 + lh // 2 + 3
    draw_lock(draw, lock_cx, lock_cy, 18, stroke=2)
    canvas.alpha_composite(ui)

    # --- Title + subtitle: Ben Tzur display type plate ---
    if spec.get("typeplate"):
        canvas, sub_bottom = overlay_typeplate(canvas, spec["typeplate"], y=78, max_w=980, max_h=255)
        if canvas.mode != "RGBA":
            canvas = canvas.convert("RGBA")
    else:
        title_font = load_font(F_EXTRABOLD, 200)
        title_layer = render_display_line(
            spec["title"], title_font, glow=True, tracking=-10, scale_x=0.78
        )
        max_title_w = int(W * 0.86)
        if title_layer.width > max_title_w:
            scale = max_title_w / title_layer.width
            title_layer = title_layer.resize(
                (max_title_w, int(title_layer.height * scale)), Image.Resampling.LANCZOS
            )
        title_bottom = paste_centered(canvas, title_layer, 168)
        sub_font = fit_font(F_BOLD, spec["subtitle"], int(W * 0.92), 46, 30)
        sub_layer = render_display_line(
            spec["subtitle"], sub_font, fill=(255, 255, 255, 250), glow=True, tracking=-2, scale_x=0.86
        )
        sub_cy = title_bottom - 8 + sub_layer.height // 2
        sub_bottom = paste_centered(canvas, sub_layer, sub_cy)

    # --- Red urgency badge ---
    badge_font = fit_font(F_EXTRABOLD, spec["badge"], W - 200, 32, 24)
    bw, bh = text_size(badge_font, spec["badge"])
    pad_x, pad_y = 38, 14
    badge_w, badge_h = bw + pad_x * 2, bh + pad_y * 2
    badge_x = (W - badge_w) // 2
    badge_y = sub_bottom + 10
    badge = rounded_rect((badge_w, badge_h), radius=badge_h // 2, fill=(214, 24, 24, 255))
    # orange/gold rim glow like Ben Tzur
    rim = rounded_rect(
        (badge_w, badge_h),
        radius=badge_h // 2,
        fill=(255, 140, 40, 255),
    )
    glow = glow_layer(rim, (255, 110, 20), radius=14, alpha=190)
    canvas.alpha_composite(glow, (badge_x - 28, badge_y - 28))
    canvas.alpha_composite(badge, (badge_x, badge_y))
    draw = ImageDraw.Draw(canvas)
    tx = badge_x + (badge_w - bw) // 2
    ty = badge_y + (badge_h - bh) // 2 - 3
    draw.text((tx, ty), spec["badge"], font=badge_font, fill=(255, 255, 255, 255))

    # --- Trust bar ---
    bar_h = 62
    bar_w = W - 2 * MARGIN
    bar_x = MARGIN
    bar_y = H - 186
    bar = rounded_rect(
        (bar_w, bar_h),
        radius=bar_h // 2,
        fill=(18, 18, 20, 175),
        outline=(255, 255, 255, 210),
        outline_width=2,
    )
    canvas.alpha_composite(bar, (bar_x, bar_y))
    draw = ImageDraw.Draw(canvas)

    trust_font = fit_font(F_SEMIBOLD, spec["trust_join"], bar_w - 140, 24, 18)
    cy = bar_y + bar_h // 2

    if spec.get("trust_left"):
        right_txt = spec["trust_right"]
        left_txt = spec["trust_left"]
        rw, _ = text_size(trust_font, right_txt)
        lw2, _ = text_size(trust_font, left_txt)
        icon_w, gap, div_w = 22, 14, 2
        total = lw2 + gap + icon_w + gap + div_w + gap + rw + gap + icon_w
        cursor = bar_x + (bar_w + total) // 2
        cursor -= icon_w
        draw_lock(draw, cursor + icon_w // 2, cy, 20)
        cursor -= gap + rw
        draw.text((cursor, cy), right_txt, font=trust_font, fill=(255, 255, 255, 255), anchor="lm")
        cursor -= gap + div_w
        draw.line((cursor, cy - 16, cursor, cy + 16), fill=(255, 255, 255, 180), width=2)
        cursor -= gap + icon_w
        draw_check_circle(draw, cursor + icon_w // 2, cy, 11)
        cursor -= gap + lw2
        draw.text((cursor, cy), left_txt, font=trust_font, fill=(255, 255, 255, 255), anchor="lm")
    else:
        txt = spec["trust_right"]
        tw2, _ = text_size(trust_font, txt)
        cluster = tw2 + 36
        start = bar_x + (bar_w - cluster) // 2
        draw.text((start, cy), txt, font=trust_font, fill=(255, 255, 255, 255), anchor="lm")
        draw_lock(draw, start + tw2 + 20, cy, 20)

    # --- CTA button ---
    cta_h = 76
    cta_w = bar_w
    cta_x = MARGIN
    cta_y = H - 108
    cta = rounded_rect((cta_w, cta_h), radius=22, fill=(255, 255, 255, 255))
    canvas.alpha_composite(cta, (cta_x, cta_y))
    draw = ImageDraw.Draw(canvas)

    cta_he_font = fit_font(F_EXTRABOLD, spec["cta_he"], 520, 34, 26)
    cta_en_font = load_font(F_BOLD, 30)
    cy2 = cta_y + cta_h // 2
    he = spec["cta_he"]
    en = "TradeTix"
    hew, _ = text_size(cta_he_font, he)
    enw, _ = text_size(cta_en_font, en)

    he_x = cta_x + cta_w - 36 - hew
    draw.text((he_x, cy2), he, font=cta_he_font, fill=(12, 12, 14, 255), anchor="lm")
    div_x = he_x - 22
    draw.line((div_x, cy2 - 16, div_x, cy2 + 16), fill=(40, 40, 45, 200), width=2)
    en_x = div_x - 20 - enw
    draw.text((en_x, cy2), en, font=cta_en_font, fill=(12, 12, 14, 255), anchor="lm")
    ch_x = cta_x + 28
    draw.polygon(
        [
            (ch_x, cy2 - 12),
            (ch_x + 14, cy2),
            (ch_x, cy2 + 12),
            (ch_x + 5, cy2 + 12),
            (ch_x + 19, cy2),
            (ch_x + 5, cy2 - 12),
        ],
        fill=(12, 12, 14, 255),
    )

    out = canvas.convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path, "PNG", optimize=True)
    out.save(ASSETS / out_path.name, "PNG", optimize=True)
    DESKTOP.mkdir(parents=True, exist_ok=True)
    out.save(DESKTOP / out_path.name, "PNG", optimize=True)
    print(f"wrote {out_path} {out.size}")


ADS = [
    {
        "bg": ASSETS / "tradetix-itay-levi-bg.png",
        "out": ROOT / "tradetix-itay-levi-urgency.png",
        "title": "איתי לוי",
        "subtitle": "קיסריה ומנורה מבטחים",
        "badge": "נשארו כרטיסים אחרונים!",
        "trust_right": "הכסף שמור בנאמנות",
        "trust_left": "קבלת כרטיס מיידית",
        "trust_join": "הכסף שמור בנאמנות קבלת כרטיס מיידית",
        "cta_he": "מצאו כרטיס עכשיו",
        "typeplate": ASSETS / "typeplate-itay-a.png",
    },
    {
        "bg": ASSETS / "tradetix-itay-levi-bg.png",
        "out": ROOT / "tradetix-itay-levi-trust.png",
        "title": "איתי לוי",
        "subtitle": "הכרטיסים המבוקשים של השנה",
        "badge": "כרטיסים אחרונים בהחלט",
        "trust_right": "תשלום מאובטח עד הכניסה למופע",
        "trust_left": None,
        "trust_join": "תשלום מאובטח עד הכניסה למופע",
        "cta_he": "לקנייה בטוחה",
        "typeplate": ASSETS / "typeplate-itay-b.png",
    },
    {
        "bg": ASSETS / "tradetix-eyal-golan-bg.png",
        "out": ROOT / "tradetix-eyal-golan-scarcity.png",
        "title": "אייל גולן",
        "subtitle": "בלומפילד 30 - כל ההופעות סולד אאוט",
        "badge": "מצאו כרטיסים אחרונים!",
        "trust_right": "100% אחריות על הכרטיסים",
        "trust_left": "העברה מיידית",
        "trust_join": "100% אחריות על הכרטיסים העברה מיידית",
        "cta_he": "שריינו כרטיס עכשיו",
        "typeplate": ASSETS / "typeplate-eyal-a.png",
    },
    {
        "bg": ASSETS / "tradetix-eyal-golan-bg.png",
        "out": ROOT / "tradetix-eyal-golan-direct.png",
        "title": "אייל גולן",
        "subtitle": "הופעות ספטמבר",
        "badge": "המלאי אוזל במהירות",
        "trust_right": "הכסף בנאמנות עד אחרי ההופעה",
        "trust_left": None,
        "trust_join": "הכסף בנאמנות עד אחרי ההופעה",
        "cta_he": "למעבר לקופה",
        "typeplate": ASSETS / "typeplate-eyal-b.png",
    },
]


if __name__ == "__main__":
    for spec in ADS:
        compose(spec["bg"], spec["out"], spec)
