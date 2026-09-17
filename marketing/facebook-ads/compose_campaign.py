"""Overlay TradeTix copy on official-looking campaign visuals (Itay cases / Eyal 30)."""

from __future__ import annotations

from pathlib import Path

from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
ASSETS = Path(r"C:\Users\user\.cursor\projects\c-Users-user-Desktop-SafeTicket\assets")
FONTS = ROOT / "fonts"
DESKTOP = Path(r"C:\Users\user\Desktop\TradeTix-ads")

W, H = 1080, 1350
MARGIN = 48
F_EX = "Gstatic-Assistant-ExtraBold.ttf"
F_BD = "Gstatic-Assistant-Bold.ttf"
F_SM = "Gstatic-Assistant-SemiBold.ttf"


def rtl(t: str) -> str:
    return get_display(t)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def tw(f, t) -> tuple[int, int]:
    b = f.getbbox(t)
    return b[2] - b[0], b[3] - b[1]


def fit(name: str, text: str, max_w: int, start: int, min_s: int = 18) -> ImageFont.FreeTypeFont:
    s = start
    while s > min_s:
        f = font(name, s)
        if tw(f, text)[0] <= max_w:
            return f
        s -= 2
    return font(name, min_s)


def cover(im: Image.Image, size, top_bias=0.35) -> Image.Image:
    tw_, th = size
    scale = max(tw_ / im.width, th / im.height)
    nw, nh = int(im.width * scale), int(im.height * scale)
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - tw_) // 2
    extra = nh - th
    top = int(extra * top_bias)
    return im.crop((left, top, left + tw_, top + th))


def fade(size, top=0, bottom=0, a_top=140, a_bot=210):
    ov = Image.new("RGBA", size, (0, 0, 0, 0))
    px = ov.load()
    w, h = size
    for y in range(top):
        a = int(a_top * (1 - y / max(top, 1)))
        for x in range(w):
            px[x, y] = (0, 0, 0, a)
    for i in range(bottom):
        y = h - 1 - i
        a = int(a_bot * (1 - i / max(bottom, 1)))
        for x in range(w):
            px[x, y] = (0, 0, 0, a)
    return ov


def rrect(size, radius, fill, outline=None, width=2):
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=fill, outline=outline, width=width)
    return im


def lock(draw, cx, cy, s, color, stroke=2, filled=True):
    bw, bh = int(s * 0.72), int(s * 0.52)
    bx, by = int(cx - bw / 2), int(cy - s * 0.02)
    if filled:
        draw.rounded_rectangle((bx, by, bx + bw, by + bh), radius=max(2, s // 7), fill=color)
    else:
        draw.rounded_rectangle((bx, by, bx + bw, by + bh), radius=max(2, s // 7), outline=color, width=stroke)
    sh_w, sh_h = int(bw * 0.58), int(s * 0.55)
    sx0 = int(cx - sh_w / 2)
    sy0 = int(by - sh_h + stroke + 2)
    draw.arc((sx0, sy0, sx0 + sh_w, sy0 + sh_h), start=200, end=340, fill=color, width=stroke)


def check(draw, cx, cy, r, color, stroke=3):
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=stroke)
    draw.line(
        [(cx - r * 0.42, cy + 0.02 * r), (cx - r * 0.08, cy + r * 0.38), (cx + r * 0.46, cy - r * 0.32)],
        fill=color,
        width=stroke,
        joint="curve",
    )


def draw_logo(draw, color, y=40):
    f = font(F_BD, 30)
    draw.text((MARGIN, y), "TradeTix", font=f, fill=color)
    w, h = tw(f, "TradeTix")
    lock(draw, MARGIN + w + 24, y + h // 2 + 3, 18, color, filled=True)


def draw_centered(draw, text, y, fnt, fill, stroke_fill=(0, 0, 0, 200), stroke_width=3):
    w, h = tw(fnt, text)
    draw.text(
        ((W - w) // 2, y),
        text,
        font=fnt,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )
    return y + h


def pill_badge(canvas, text, y, fill, text_fill, glow=None, size=34, max_w=None):
    f = fit(F_EX, text, max_w or (W - 160), size, 22)
    bw, bh = tw(f, text)
    pad_x, pad_y = 40, 16
    pw, ph = bw + pad_x * 2, bh + pad_y * 2
    x = (W - pw) // 2
    badge = rrect((pw, ph), ph // 2, fill)
    if glow:
        a = badge.split()[-1]
        g = Image.new("RGBA", badge.size, glow + (180,))
        g.putalpha(a)
        pad = 28
        padded = Image.new("RGBA", (pw + pad * 2, ph + pad * 2), (0, 0, 0, 0))
        padded.paste(g, (pad, pad), g)
        canvas.alpha_composite(padded.filter(ImageFilter.GaussianBlur(10)), (x - pad, y - pad))
    canvas.alpha_composite(badge, (x, y))
    d = ImageDraw.Draw(canvas)
    d.text((x + (pw - bw) // 2, y + (ph - bh) // 2 - 2), text, font=f, fill=text_fill)
    return y + ph


def cta_button(canvas, he, y, bg, fg, radius=20):
    bar_w = W - 2 * MARGIN
    bar_h = 78
    x = MARGIN
    canvas.alpha_composite(rrect((bar_w, bar_h), radius, bg), (x, y))
    d = ImageDraw.Draw(canvas)
    hf = fit(F_EX, he, 540, 34, 24)
    ef = font(F_BD, 30)
    cy = y + bar_h // 2
    hew, _ = tw(hf, he)
    enw, _ = tw(ef, "TradeTix")
    he_x = x + bar_w - 36 - hew
    d.text((he_x, cy), he, font=hf, fill=fg, anchor="lm")
    div = he_x - 20
    d.line((div, cy - 16, div, cy + 16), fill=fg, width=2)
    d.text((div - 18 - enw, cy), "TradeTix", font=ef, fill=fg, anchor="lm")
    ch = x + 28
    d.polygon(
        [(ch, cy - 12), (ch + 14, cy), (ch, cy + 12), (ch + 5, cy + 12), (ch + 19, cy), (ch + 5, cy - 12)],
        fill=fg,
    )


def trust_bar(canvas, right, left, y, fill, outline, fg):
    bar_w = W - 2 * MARGIN
    bar_h = 60
    x = MARGIN
    canvas.alpha_composite(rrect((bar_w, bar_h), bar_h // 2, fill, outline, 2), (x, y))
    d = ImageDraw.Draw(canvas)
    join = right + (left or "")
    f = fit(F_SM, join, bar_w - 120, 23, 16)
    cy = y + bar_h // 2
    if left:
        rw, _ = tw(f, right)
        lw, _ = tw(f, left)
        icon, gap = 20, 12
        total = lw + gap + icon + gap + 2 + gap + rw + gap + icon
        cur = x + (bar_w + total) // 2
        cur -= icon
        lock(d, cur + icon // 2, cy, 18, fg, filled=False)
        cur -= gap + rw
        d.text((cur, cy), right, font=f, fill=fg, anchor="lm")
        cur -= gap + 2
        d.line((cur, cy - 14, cur, cy + 14), fill=fg, width=2)
        cur -= gap + icon
        check(d, cur + icon // 2, cy, 10, fg)
        cur -= gap + lw
        d.text((cur, cy), left, font=f, fill=fg, anchor="lm")
    else:
        rw, _ = tw(f, right)
        start = x + (bar_w - (rw + 36)) // 2
        d.text((start, cy), right, font=f, fill=fg, anchor="lm")
        lock(d, start + rw + 20, cy, 18, fg, filled=False)


def save(im: Image.Image, name: str):
    out = ROOT / name
    im.convert("RGB").save(out, "PNG", optimize=True)
    im.convert("RGB").save(ASSETS / name, "PNG", optimize=True)
    DESKTOP.mkdir(exist_ok=True)
    im.convert("RGB").save(DESKTOP / name, "PNG", optimize=True)
    print("wrote", out)


def compose_itay(spec):
    bg = cover(Image.open(spec["bg"]).convert("RGB"), (W, H), top_bias=0.42)
    canvas = bg.convert("RGBA")
    canvas.alpha_composite(fade((W, H), top=220, bottom=400, a_top=130, a_bot=210))
    # extra mid-frame dim so the ticket line pops in the center
    mid = fade((W, H), top=0, bottom=0)
    px = mid.load()
    for y in range(480, 760):
        dist = min(y - 480, 760 - y)
        a = int(90 * (dist / 140))
        a = min(a, 90)
        for x in range(W):
            px[x, y] = (0, 0, 0, a)
    canvas.alpha_composite(mid)

    d = ImageDraw.Draw(canvas)
    draw_logo(d, (255, 255, 255, 255), y=32)

    title = rtl(spec["title"])
    sub = rtl(spec["subtitle"])
    tf = fit(F_EX, title, W - 100, 78, 56)
    y = 78
    y = draw_centered(d, title, y, tf, (255, 255, 255, 255), stroke_width=2) + 8
    sf = fit(F_EX, sub, W - 120, 34, 24)
    y = draw_centered(d, sub, y, sf, (255, 255, 255, 245), stroke_width=2, stroke_fill=(0, 0, 0, 160)) + 6

    # Ticket line is the hero — large, centered on his torso
    pill_badge(
        canvas,
        rtl(spec["badge"]),
        560,
        (214, 24, 24, 255),
        (255, 255, 255, 255),
        glow=(255, 70, 40),
        size=44,
        max_w=W - 80,
    )

    trust_bar(
        canvas,
        rtl(spec["trust_right"]),
        rtl(spec["trust_left"]) if spec.get("trust_left") else None,
        H - 186,
        (12, 12, 14, 180),
        (255, 255, 255, 210),
        (255, 255, 255, 255),
    )
    cta_button(canvas, rtl(spec["cta"]), H - 112, (255, 255, 255, 255), (12, 12, 14, 255))
    save(canvas, spec["out"])


def compose_eyal(spec):
    raw = Image.open(spec["bg"]).convert("RGB")
    red_c = raw.getpixel((16, 16))
    fitted = cover(raw, (W, H), top_bias=0.10)
    scale = 0.90
    nw, nh = int(W * scale), int(H * scale)
    small = fitted.resize((nw, nh), Image.Resampling.LANCZOS)
    base = Image.new("RGB", (W, H), red_c)
    base.paste(small, ((W - nw) // 2, 6))
    canvas = base.convert("RGBA")
    canvas.alpha_composite(fade((W, H), top=0, bottom=260, a_top=0, a_bot=70))
    d = ImageDraw.Draw(canvas)
    yellow = (255, 214, 0, 255)
    red = (196, 16, 22, 255)
    draw_logo(d, yellow, y=34)

    pill_badge(canvas, rtl(spec["badge"]), H - 280, yellow, red, glow=(255, 200, 40), size=36)

    trust_bar(
        canvas,
        rtl(spec["trust_right"]),
        rtl(spec["trust_left"]) if spec.get("trust_left") else None,
        H - 186,
        (140, 8, 12, 200),
        yellow,
        yellow,
    )
    cta_button(canvas, rtl(spec["cta"]), H - 112, yellow, red, radius=18)
    save(canvas, spec["out"])


ITAY = [
    {
        "bg": ASSETS / "itay-official-bg.png",
        "out": "tradetix-itay-levi-urgency.png",
        "title": "איתי לוי",
        "subtitle": "קיסריה ומנורה מבטחים",
        "badge": "נשארו כרטיסים אחרונים!",
        "trust_right": "הכסף שמור בנאמנות",
        "trust_left": "קבלת כרטיס מיידית",
        "cta": "מצאו כרטיס עכשיו",
    },
    {
        "bg": ASSETS / "itay-official-bg.png",
        "out": "tradetix-itay-levi-trust.png",
        "title": "איתי לוי",
        "subtitle": "הכרטיסים המבוקשים של השנה",
        "badge": "כרטיסים אחרונים בהחלט",
        "trust_right": "תשלום מאובטח עד הכניסה למופע",
        "trust_left": None,
        "cta": "לקנייה בטוחה",
    },
]

EYAL = [
    {
        "bg": ASSETS / "eyal-official-bg.png",
        "out": "tradetix-eyal-golan-scarcity.png",
        "badge": "מצאו כרטיסים אחרונים!",
        "trust_right": "100% אחריות על הכרטיסים",
        "trust_left": "העברה מיידית",
        "cta": "שריינו כרטיס עכשיו",
    },
    {
        "bg": ASSETS / "eyal-official-bg.png",
        "out": "tradetix-eyal-golan-direct.png",
        "badge": "המלאי אוזל במהירות",
        "trust_right": "הכסף בנאמנות עד אחרי ההופעה",
        "trust_left": None,
        "cta": "למעבר לקופה",
    },
]


if __name__ == "__main__":
    for s in ITAY:
        compose_itay(s)
    for s in EYAL:
        compose_eyal(s)
