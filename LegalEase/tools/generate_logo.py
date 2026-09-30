"""Create the placeholder logos. Replace Image/Logo.png and Image/inverseLogo.png with your own any time.
Run from the project folder:  python tools/generate_logo.py"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "Image"


def make(path, fg, bg):
    w, h = 600, 200
    img = Image.new("RGBA", (w, h), bg)
    d = ImageDraw.Draw(img)
    # simple scales-of-justice mark
    cx, top = 100, 40
    d.line([(cx, top), (cx, 160)], fill=fg, width=6)
    d.line([(cx - 55, top + 15), (cx + 55, top + 15)], fill=fg, width=6)
    d.line([(cx - 40, 165), (cx + 40, 165)], fill=fg, width=6)
    for x in (cx - 55, cx + 55):
        d.line([(x, top + 15), (x - 22, top + 70)], fill=fg, width=3)
        d.line([(x, top + 15), (x + 22, top + 70)], fill=fg, width=3)
        d.arc([x - 25, top + 55, x + 25, top + 85], 0, 180, fill=fg, width=5)
    try:
        font = ImageFont.load_default(size=64)
    except TypeError:  # very old Pillow
        font = ImageFont.load_default()
    d.text((190, 62), "LegalEase", fill=fg, font=font)
    img.save(path)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    make(OUT / "Logo.png", (20, 40, 80, 255), (255, 255, 255, 0))
    make(OUT / "inverseLogo.png", (240, 244, 250, 255), (0, 0, 0, 0))
    print("Logos written to", OUT)
