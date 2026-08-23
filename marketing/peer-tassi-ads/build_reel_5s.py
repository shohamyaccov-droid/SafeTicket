"""Build a 5s 9:16 TradeTix Reels MP4 from AI keyframes + Hebrew overlays."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(r"C:\Users\user\.cursor\projects\c-Users-user-Desktop-SafeTicket\assets")
OUT_DIR = Path(r"C:\Users\user\Desktop\SafeTicket\marketing\peer-tassi-ads")
W, H = 1080, 1920
FPS = 30
DURATION = 5.0
N = int(FPS * DURATION)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\tahoma.ttf",
]
FONT_PATH = next((p for p in FONT_CANDIDATES if Path(p).exists()), None)


def load_cover(name: str) -> Image.Image:
    im = Image.open(ASSETS / name).convert("RGB")
    scale = max(W / im.width, H / im.height)
    nw, nh = int(im.width * scale), int(im.height * scale)
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - W) // 2
    top = (nh - H) // 2
    return im.crop((left, top, left + W, top + H))


def lerp_img(a: Image.Image, b: Image.Image, t: float) -> Image.Image:
    t = max(0.0, min(1.0, t))
    arr = np.asarray(a, dtype=np.float32) * (1 - t) + np.asarray(b, dtype=np.float32) * t
    return Image.fromarray(arr.astype(np.uint8))


def base_at(t: float, f1: Image.Image, f2: Image.Image, f3: Image.Image) -> Image.Image:
    if t < 1.4:
        return f1
    if t < 1.7:
        return lerp_img(f1, f2, (t - 1.4) / 0.3)
    if t < 2.4:
        return f2
    if t < 2.7:
        return lerp_img(f2, f3, (t - 2.4) / 0.3)
    return f3


def he(text: str) -> str:
    """Visual reorder for correct Hebrew rendering without libraqm."""
    return get_display(text)


def fit_text(draw: ImageDraw.ImageDraw, text: str, font_size: int, max_width: int) -> ImageFont.FreeTypeFont:
    visual = he(text)
    font = ImageFont.truetype(FONT_PATH, font_size)
    while font_size > 22:
        bbox = draw.textbbox((0, 0), visual, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
        font_size -= 2
        font = ImageFont.truetype(FONT_PATH, font_size)
    return font


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    fill,
    font_size: int = 64,
    stroke: int = 3,
    stroke_fill=(0, 0, 0),
) -> None:
    visual = he(text)
    font = fit_text(draw, text, font_size, W - 80)
    bbox = draw.textbbox((0, 0), visual, font=font)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    draw.text(
        (x, y),
        visual,
        font=font,
        fill=fill,
        stroke_width=stroke,
        stroke_fill=stroke_fill,
        align="center",
    )


def draw_pill_button(img: Image.Image, text: str, y: int) -> None:
    draw = ImageDraw.Draw(img)
    visual = he(text)
    font = fit_text(draw, text, 42, W - 160)
    bbox = draw.textbbox((0, 0), visual, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 48, 22
    bw, bh = tw + pad_x * 2, th + pad_y * 2
    x0 = (W - bw) // 2
    draw.rounded_rectangle(
        [x0, y, x0 + bw, y + bh],
        radius=bh // 2,
        fill=(8, 180, 210),
        outline=(180, 255, 255),
        width=3,
    )
    draw.text((x0 + pad_x, y + pad_y - 2), visual, font=font, fill=(255, 255, 255))


def overlay(im: Image.Image, t: float) -> Image.Image:
    img = im.copy()
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    if t < 2.6:
        sd.rectangle([0, 0, W, 420], fill=(0, 0, 0, 130))
    else:
        sd.rectangle([0, int(H * 0.45), W, H], fill=(0, 0, 0, 160))
    img = Image.alpha_composite(img.convert("RGBA"), shade).convert("RGB")
    draw = ImageDraw.Draw(img)

    hook = 'נמאס מ"עוד רלוונטי?"'
    sub = "מוכרים כרטיס בפייסבוק?"
    money = "100% מהכסף אליך"
    gift = "₪20 מתנה לכל כרטיס שיימכר"
    cta = "העלו ב-TradeTix עכשיו"
    foot = "tradetix.co.il · מכירה מאובטחת"

    if t < 2.55:
        draw_centered_text(draw, hook, 120, (255, 255, 255), font_size=70, stroke=4)
        if t > 1.2:
            draw_centered_text(draw, sub, 240, (255, 200, 200), font_size=44, stroke=3)
    else:
        draw_centered_text(draw, money, int(H * 0.52), (255, 255, 255), font_size=68, stroke=4)
        draw_centered_text(draw, gift, int(H * 0.60), (80, 230, 255), font_size=40, stroke=3)
        draw_pill_button(img, cta, int(H * 0.72))
        draw2 = ImageDraw.Draw(img)
        draw_centered_text(draw2, foot, int(H * 0.84), (180, 230, 255), font_size=32, stroke=2)
    return img


def main() -> None:
    if not FONT_PATH:
        raise SystemExit("No Hebrew-capable TrueType font found on Windows Fonts.")
    print("font:", FONT_PATH)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    f1 = load_cover("reel-frame-01-chaos.png")
    f2 = load_cover("reel-frame-02-stress.png")
    f3 = load_cover("reel-frame-03-calm.png")

    tmp = OUT_DIR / "_reel_frames"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()

    print("rendering frames...")
    for i in range(N):
        t = i / FPS
        frame = overlay(base_at(t, f1, f2, f3), t)
        if t < 1.5:
            z = 1.0 + 0.03 * (t / 1.5)
            zw, zh = int(W * z), int(H * z)
            zoomed = frame.resize((zw, zh), Image.Resampling.BILINEAR)
            left = (zw - W) // 2
            top = (zh - H) // 2
            frame = zoomed.crop((left, top, left + W, top + H))
        frame.save(tmp / f"f{i:04d}.png")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    out_mp4 = OUT_DIR / "tradetix-reel-od-relevanti-5s.mp4"
    cmd = [
        ffmpeg,
        "-y",
        "-framerate",
        str(FPS),
        "-i",
        str(tmp / "f%04d.png"),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "high",
        "-crf",
        "18",
        "-movflags",
        "+faststart",
        "-t",
        str(DURATION),
        str(out_mp4),
    ]
    print("encoding...")
    subprocess.check_call(cmd)
    shutil.rmtree(tmp)
    print("DONE", out_mp4)
    print("size_mb", round(out_mp4.stat().st_size / 1e6, 2))


if __name__ == "__main__":
    main()
