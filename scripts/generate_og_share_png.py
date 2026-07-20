"""Generate frontend/public/og-share.png with Hebrew text baked in (Facebook-safe)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
OUT = Path(__file__).resolve().parents[1] / 'frontend' / 'public' / 'og-share.png'


def main() -> None:
    img = Image.new('RGB', (W, H), '#001a44')
    draw = ImageDraw.Draw(img)

    # Gradient: #0045af -> #001a44
    for y in range(H):
        t = y / (H - 1)
        r = int(0x00 * (1 - t) + 0x00 * t)
        g = int(0x45 * (1 - t) + 0x1a * t)
        b = int(0xaf * (1 - t) + 0x44 * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    font_bold = ImageFont.truetype(r'C:\Windows\Fonts\arialbd.ttf', 84)
    font_reg = ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf', 36)

    title = 'TradeTix'
    subtitle = 'זירת מסחר בטוחה לכרטיסים בישראל'

    def center_text(text: str, font, y: int, fill: str) -> None:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        x = (W - tw) / 2
        draw.text((x, y), text, font=font, fill=fill)

    center_text(title, font_bold, 210, '#ffffff')
    center_text(subtitle, font_reg, 320, '#c7d7ff')

    bar_w, bar_h = 360, 8
    bx = (W - bar_w) // 2
    by = 420
    draw.rounded_rectangle([bx, by, bx + bar_w, by + bar_h], radius=4, fill='#4ade80')

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, format='PNG', optimize=True)
    print(f'wrote {OUT} ({OUT.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
