"""Build a ~10s 9:16 TradeTix Reels MP4: pacing, SFX, pulse CTA, neon gift."""
from __future__ import annotations

import math
import shutil
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ASSETS = Path(r"C:\Users\user\.cursor\projects\c-Users-user-Desktop-SafeTicket\assets")
OUT_DIR = Path(r"C:\Users\user\Desktop\SafeTicket\marketing\peer-tassi-ads")
W, H = 1080, 1920
FPS = 30
DURATION = 10.0
N = int(FPS * DURATION)
SR = 44100

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
]
FONT_PATH = next((p for p in FONT_CANDIDATES if Path(p).exists()), None)


def he(text: str) -> str:
    return get_display(text)


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
    # 0-2.4 chaos, 2.4-3.0 stress peek, 3.0-4.0 transition to calm, 4-10 calm
    if t < 2.2:
        return f1
    if t < 2.6:
        return lerp_img(f1, f2, (t - 2.2) / 0.4)
    if t < 3.0:
        return f2
    if t < 3.9:
        return lerp_img(f2, f3, (t - 3.0) / 0.9)
    return f3


def fit_text(draw: ImageDraw.ImageDraw, text: str, font_size: int, max_width: int) -> ImageFont.FreeTypeFont:
    visual = he(text)
    font = ImageFont.truetype(FONT_PATH, font_size)
    while font_size > 20:
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
    max_width: int | None = None,
) -> tuple[int, int, int, int]:
    visual = he(text)
    font = fit_text(draw, text, font_size, max_width or (W - 80))
    bbox = draw.textbbox((0, 0), visual, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
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
    return (x, y, x + tw, y + th)


def draw_pill_button(img: Image.Image, text: str, y: int, scale: float = 1.0) -> tuple[int, int, int, int]:
    draw = ImageDraw.Draw(img)
    visual = he(text)
    base_size = int(44 * scale)
    font = fit_text(draw, text, base_size, int((W - 160) / max(scale, 0.8)))
    bbox = draw.textbbox((0, 0), visual, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = int(52 * scale), int(24 * scale)
    bw, bh = tw + pad_x * 2, th + pad_y * 2
    x0 = (W - bw) // 2
    # glow
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    expand = int(10 * scale)
    gd.rounded_rectangle(
        [x0 - expand, y - expand, x0 + bw + expand, y + bh + expand],
        radius=(bh + expand * 2) // 2,
        fill=(40, 220, 255, int(90 * min(scale, 1.25))),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(12))
    img_rgba = Image.alpha_composite(img.convert("RGBA"), glow)
    draw = ImageDraw.Draw(img_rgba)
    draw.rounded_rectangle(
        [x0, y, x0 + bw, y + bh],
        radius=bh // 2,
        fill=(0, 200, 220, 255),
        outline=(200, 255, 255, 255),
        width=4,
    )
    draw.text((x0 + pad_x, y + pad_y - 2), visual, font=font, fill=(255, 255, 255, 255))
    img.paste(img_rgba.convert("RGB"))
    return (x0, y, x0 + bw, y + bh)


def draw_tap_finger(img: Image.Image, cx: int, cy: int, press: float) -> None:
    """Simple finger/pointer cue that 'taps' the CTA."""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    y_off = int(28 * (1 - press))
    # pointer circle + tip
    r = 28
    x, y = cx + 40, cy + 20 + y_off
    d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 210), outline=(0, 180, 220, 255), width=4)
    d.polygon([(x - 8, y + r - 4), (x + 18, y + r + 36), (x + 4, y + r + 8)], fill=(255, 255, 255, 210))
    # tap ripple
    if press > 0.7:
        rr = int(40 + 30 * press)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(120, 255, 255, 160), width=3)
    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))


def overlay(im: Image.Image, t: float) -> Image.Image:
    img = im.copy()
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    if t < 3.0:
        sd.rectangle([0, 0, W, 480], fill=(0, 0, 0, 140))
    elif t < 4.0:
        sd.rectangle([0, int(H * 0.35), W, int(H * 0.7)], fill=(0, 0, 0, 150))
    else:
        sd.rectangle([0, int(H * 0.42), W, H], fill=(0, 0, 0, 170))
    img = Image.alpha_composite(img.convert("RGBA"), shade).convert("RGB")
    draw = ImageDraw.Draw(img)

    hook = 'נמאס מ"עוד רלוונטי?"'
    sub = "מוכרים כרטיס בפייסבוק?"
    bridge = "יש דרך חכמה יותר."
    money = "100% מהכסף אליך"
    gift = "₪20 מתנה"
    gift2 = "לכל כרטיס שיימכר"
    cta = "העלו ב-TradeTix עכשיו"
    foot = "tradetix.co.il · מכירה מאובטחת"

    if t < 3.0:
        # Pain — give time to read
        alpha_boost = min(1.0, t / 0.4)
        draw_centered_text(draw, hook, 110, (255, 255, 255), font_size=72, stroke=5)
        if t > 0.8:
            draw_centered_text(draw, sub, 250, (255, 190, 190), font_size=46, stroke=3)
        if t > 1.6:
            draw_centered_text(
                draw,
                'עוד רלוונטי? עוד רלוונטי? עוד רלוונטי?',
                340,
                (255, 120, 120),
                font_size=34,
                stroke=2,
            )
        _ = alpha_boost
    elif t < 4.0:
        # Transition bridge line — appear then fade
        local = (t - 3.0) / 1.0
        # fade in 0-0.35, hold, fade out 0.75-1.0
        if local < 0.35:
            fade = local / 0.35
        elif local > 0.75:
            fade = (1.0 - local) / 0.25
        else:
            fade = 1.0
        c = int(255 * fade)
        draw_centered_text(draw, bridge, int(H * 0.48), (c, 240, 255), font_size=58, stroke=4, stroke_fill=(0, 0, 0))
    else:
        # Solution 4-10s — stay readable
        draw_centered_text(draw, money, int(H * 0.48), (255, 255, 255), font_size=70, stroke=5)
        # Neon gift — yellow/green, larger
        draw_centered_text(
            draw,
            gift,
            int(H * 0.56),
            (255, 240, 40),
            font_size=78,
            stroke=5,
            stroke_fill=(0, 80, 0),
        )
        draw_centered_text(
            draw,
            gift2,
            int(H * 0.62),
            (120, 255, 100),
            font_size=44,
            stroke=3,
            stroke_fill=(0, 40, 0),
        )

        # Pulse every 2 seconds
        pulse_phase = ((t - 4.0) % 2.0) / 2.0
        pulse = 1.0 + 0.08 * abs(math.sin(pulse_phase * math.pi))
        btn = draw_pill_button(img, cta, int(H * 0.72), scale=pulse)

        # Finger tap near peak of pulse (every 2s)
        if 0.35 < pulse_phase < 0.65:
            press = (pulse_phase - 0.35) / 0.3
            cx = (btn[0] + btn[2]) // 2
            cy = (btn[1] + btn[3]) // 2
            draw_tap_finger(img, cx, cy, press)

        draw2 = ImageDraw.Draw(img)
        draw_centered_text(draw2, foot, int(H * 0.88), (180, 235, 255), font_size=30, stroke=2)

        # Soft escrow trust line
        if t > 4.8:
            draw_centered_text(
                draw2,
                "הכסף נשמר בנאמנות",
                int(H * 0.68),
                (200, 230, 255),
                font_size=32,
                stroke=2,
            )
    return img


# ---------------- audio ----------------
def tone(freq: float, dur: float, vol: float = 0.3, decay: bool = True) -> np.ndarray:
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    wave_ = np.sin(2 * np.pi * freq * t)
    if decay:
        env = np.exp(-t * (4.0 / max(dur, 0.05)))
    else:
        env = np.ones_like(t)
        env[: int(0.01 * SR)] = np.linspace(0, 1, int(0.01 * SR))
        env[-int(0.02 * SR) :] *= np.linspace(1, 0, int(0.02 * SR))
    return (wave_ * env * vol).astype(np.float32)


def noise_burst(dur: float, vol: float = 0.25) -> np.ndarray:
    n = int(SR * dur)
    x = np.random.randn(n).astype(np.float32)
    env = np.linspace(0, 1, n // 5)
    env = np.concatenate([env, np.ones(n - len(env) - n // 3), np.linspace(1, 0, n // 3)])
    if len(env) < n:
        env = np.pad(env, (0, n - len(env)))
    env = env[:n]
    # whoosh: highpass-ish by differentiating
    x = np.diff(x, prepend=x[:1])
    return x * env * vol


def mix_audio(path: Path) -> None:
    total = int(SR * DURATION)
    buf = np.zeros(total, dtype=np.float32)

    def add_at(start: float, clip: np.ndarray) -> None:
        i = int(start * SR)
        j = min(total, i + len(clip))
        buf[i:j] += clip[: j - i]

    # Stress notifications 0-3s, accelerating
    t = 0.0
    gap = 0.28
    while t < 3.0:
        vol = 0.12 + 0.28 * (t / 3.0)
        freq = 880 + 200 * (t / 3.0)
        add_at(t, tone(freq, 0.07, vol=vol))
        add_at(t + 0.02, tone(1175, 0.05, vol=vol * 0.7))
        t += gap
        gap = max(0.09, gap * 0.92)

    # Whoosh cuts the noise ~3.0-3.6
    add_at(2.95, noise_burst(0.55, vol=0.35))
    add_at(3.05, tone(180, 0.4, vol=0.15))

    # Soft lo-fi pad 4-10s (gentle sine stack)
    pad_len = int(SR * 6.2)
    tt = np.linspace(0, 6.2, pad_len, endpoint=False)
    pad = (
        0.04 * np.sin(2 * np.pi * 110 * tt)
        + 0.03 * np.sin(2 * np.pi * 165 * tt)
        + 0.025 * np.sin(2 * np.pi * 220 * tt)
    ).astype(np.float32)
    # slow tremolo
    pad *= (0.75 + 0.25 * np.sin(2 * np.pi * 0.4 * tt)).astype(np.float32)
    add_at(3.9, pad)

    # Cha-ching when offer/CTA lands (~4.2) and on pulses (~6.2, 8.2)
    def chaching(start: float) -> None:
        add_at(start, tone(1319, 0.08, vol=0.35))
        add_at(start + 0.07, tone(1760, 0.18, vol=0.28))
        add_at(start + 0.05, tone(2093, 0.12, vol=0.18))

    chaching(4.15)
    chaching(6.15)
    chaching(8.15)

    # soft click on finger taps
    for tap_t in (4.9, 6.9, 8.9):
        add_at(tap_t, tone(600, 0.04, vol=0.12))

    peak = np.max(np.abs(buf)) or 1.0
    buf = np.clip(buf / peak * 0.9, -1, 1)
    pcm = (buf * 32767).astype(np.int16)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())


def main() -> None:
    if not FONT_PATH:
        raise SystemExit("No font found")
    print("font:", FONT_PATH)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    f1 = load_cover("reel-frame-01-chaos.png")
    f2 = load_cover("reel-frame-02-stress.png")
    f3 = load_cover("reel-frame-03-calm.png")

    tmp = OUT_DIR / "_reel_frames_v2"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()

    print("rendering frames...")
    for i in range(N):
        t = i / FPS
        frame = overlay(base_at(t, f1, f2, f3), t)
        # intensifying zoom during pain
        if t < 3.0:
            z = 1.0 + 0.06 * (t / 3.0)
            zw, zh = int(W * z), int(H * z)
            zoomed = frame.resize((zw, zh), Image.Resampling.BILINEAR)
            left = (zw - W) // 2
            top = (zh - H) // 2
            frame = zoomed.crop((left, top, left + W, top + H))
            # micro shake late in pain
            if t > 1.5:
                shake = int(4 * ((t - 1.5) / 1.5))
                ox = int(shake * math.sin(t * 40))
                oy = int(shake * math.cos(t * 35))
                shaken = Image.new("RGB", (W, H), (10, 0, 0))
                shaken.paste(frame, (ox, oy))
                frame = shaken
        frame.save(tmp / f"f{i:04d}.png")

    wav_path = OUT_DIR / "_reel_audio.wav"
    print("mixing audio...")
    mix_audio(wav_path)

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    out_mp4 = OUT_DIR / "tradetix-reel-od-relevanti-10s.mp4"
    cmd = [
        ffmpeg,
        "-y",
        "-framerate",
        str(FPS),
        "-i",
        str(tmp / "f%04d.png"),
        "-i",
        str(wav_path),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "high",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(out_mp4),
    ]
    print("encoding...")
    subprocess.check_call(cmd)
    shutil.rmtree(tmp)
    wav_path.unlink(missing_ok=True)

    # previews
    for ss, name in (("1.5", "reel-v2-preview-pain.jpg"), ("3.4", "reel-v2-preview-bridge.jpg"), ("6.0", "reel-v2-preview-cta.jpg")):
        subprocess.check_call(
            [ffmpeg, "-y", "-ss", ss, "-i", str(out_mp4), "-frames:v", "1", str(OUT_DIR / name)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    print("DONE", out_mp4)
    print("size_mb", round(out_mp4.stat().st_size / 1e6, 2))


if __name__ == "__main__":
    main()
