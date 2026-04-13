"""Generate design/nura_favicon.png — 32x32 with #1e1e2e bg and N in #60a0ff."""
from PIL import Image, ImageDraw, ImageFont
import os

SIZE = 32
out = os.path.join(os.path.dirname(__file__), "nura_favicon.png")

img = Image.new("RGBA", (SIZE, SIZE), (30, 30, 46, 255))   # #1e1e2e
draw = ImageDraw.Draw(img)

font = None
font_size = 22
for candidate in [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
    "C:/Windows/Fonts/seguibl.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
]:
    if os.path.exists(candidate):
        try:
            font = ImageFont.truetype(candidate, font_size)
            break
        except Exception:
            pass

text = "N"
color = (0x60, 0xa0, 0xFF, 255)   # #60a0ff

if font:
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (SIZE - w) // 2 - bbox[0]
    y = (SIZE - h) // 2 - bbox[1]
    draw.text((x, y), text, fill=color, font=font)
else:
    draw.text((10, 8), text, fill=color)

img.save(out, "PNG")
print(f"Saved {out}")
