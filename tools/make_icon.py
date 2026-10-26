"""Render the Keyhold app icon (SVG, PNG and ICO) into keyhold/assets/.

Run from the repo root:  python tools/make_icon.py   (needs Pillow)
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "keyhold" / "assets"

# Colours from keyhold/ui/theme.py
SURFACE = "#18191c"
BORDER = "#2a2b30"
TEXT = "#e8e8ea"

# Geometry on a 256-unit canvas
TILE = (16, 16, 240, 240)
RADIUS = 52
STROKE = 3
HOLE_CENTER = (128, 102)
HOLE_RADIUS = 34
SLOT = [(115, 116), (141, 116), (152, 187), (104, 187)]

SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <rect x="{TILE[0] + STROKE / 2}" y="{TILE[1] + STROKE / 2}" width="{TILE[2] - TILE[0] - STROKE}" \
height="{TILE[3] - TILE[1] - STROKE}" rx="{RADIUS - STROKE / 2}" fill="{SURFACE}" stroke="{BORDER}" \
stroke-width="{STROKE}"/>
  <g fill="{TEXT}">
    <circle cx="{HOLE_CENTER[0]}" cy="{HOLE_CENTER[1]}" r="{HOLE_RADIUS}"/>
    <polygon points="{" ".join(f"{x},{y}" for x, y in SLOT)}"/>
  </g>
</svg>
"""


def render(size: int) -> Image.Image:
    ss = 4  # supersample, then downscale for clean edges
    scale = size * ss / 256
    img = Image.new("RGBA", (size * ss, size * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(
        [v * scale for v in TILE],
        radius=RADIUS * scale,
        fill=SURFACE,
        outline=BORDER,
        width=max(1, round(STROKE * scale)),
    )
    cx, cy = HOLE_CENTER
    r = HOLE_RADIUS
    d.ellipse([(cx - r) * scale, (cy - r) * scale, (cx + r) * scale, (cy + r) * scale], fill=TEXT)
    d.polygon([(x * scale, y * scale) for x, y in SLOT], fill=TEXT)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "icon.svg").write_text(SVG, encoding="utf-8")
    render(512).save(OUT / "icon.png")
    render(256).save(OUT / "icon.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print(f"Wrote icon.svg, icon.png, icon.ico to {OUT}")


if __name__ == "__main__":
    main()
