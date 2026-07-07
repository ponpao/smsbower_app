"""Generate the placeholder app icon: violet rounded-square "G" mark.

Writes assets/icons/grok_studio.ico (multi-size) + grok_studio.png.
Requires Pillow:  pip install Pillow
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ACCENT = (124, 92, 255, 255)        # #7C5CFF
SIZES = [16, 24, 32, 48, 64, 128, 256]


def draw_mark(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = max(2, size * 12 // 64)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=ACCENT)

    text = "G"
    font = None
    for candidate in ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(candidate, int(size * 0.62))
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]),
        text, font=font, fill=(255, 255, 255, 255),
    )
    return img


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "assets" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)

    base = draw_mark(256)
    base.save(out_dir / "grok_studio.png")
    base.save(
        out_dir / "grok_studio.ico",
        sizes=[(s, s) for s in SIZES],
    )
    print(f"wrote {out_dir / 'grok_studio.ico'}")


if __name__ == "__main__":
    main()
