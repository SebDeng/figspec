"""Generate a placeholder app icon (grid glyph) -> AppIcon.icns via iconutil."""
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).parent / "assets"


def draw(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = size // 8
    d.rounded_rectangle([m, m, size - m, size - m], radius=size // 6,
                        fill=(15, 77, 146, 255))
    # panel grid glyph: one tall left panel, two stacked right panels
    g = size // 24
    x0, y0, x1, y1 = 2 * m, 2 * m, size - 2 * m, size - 2 * m
    mid_x = (x0 + x1) // 2
    mid_y = (y0 + y1) // 2
    white = (250, 250, 250, 255)
    d.rounded_rectangle([x0, y0, mid_x - g, y1], radius=g, fill=white)
    d.rounded_rectangle([mid_x + g, y0, x1, mid_y - g], radius=g, fill=white)
    d.rounded_rectangle([mid_x + g, mid_y + g, x1, y1], radius=g, fill=white)
    return img


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        iconset = Path(td) / "AppIcon.iconset"
        iconset.mkdir()
        for pts in (16, 32, 64, 128, 256, 512):
            draw(pts).save(iconset / f"icon_{pts}x{pts}.png")
            draw(pts * 2).save(iconset / f"icon_{pts}x{pts}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset),
                        "-o", str(OUT / "AppIcon.icns")], check=True)
    print(f"wrote {OUT / 'AppIcon.icns'}")


if __name__ == "__main__":
    main()
