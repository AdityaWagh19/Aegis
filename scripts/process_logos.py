"""Process brand logos for web use: crop to content, make background transparent, downscale."""
from PIL import Image
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUB = ROOT / "dashboard" / "public"
PUB.mkdir(exist_ok=True)


def process_web_lockup():
    """Aegis_web.png: blue mark + wordmark on black -> transparent, cropped, web-sized."""
    img = Image.open(ROOT / "assets" / "Aegis_web.png").convert("RGBA")
    px = img.load()
    w, h = img.size
    # Black background -> transparent (threshold catches anti-aliased edges)
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r < 40 and g < 40 and b < 40:
                px[x, y] = (r, g, b, 0)
    # Crop to visible content
    bbox = img.getbbox()
    img = img.crop(bbox)
    # Resize to a sensible nav height (keep aspect; target height 160px master -> rendered at 28px)
    ratio = 160 / img.height
    img = img.resize((max(1, int(img.width * ratio)), 160), Image.LANCZOS)
    img.save(PUB / "aegis-logo.png", optimize=True)
    print(f"aegis-logo.png: {img.size}")


def process_favicon():
    """Aegis_logo.png: full-bleed mark -> square PNG at 256px for favicon."""
    img = Image.open(ROOT / "assets" / "Aegis_logo.png").convert("RGBA")
    img = img.resize((256, 256), Image.LANCZOS)
    img.save(PUB / "favicon.png", optimize=True)
    print(f"favicon.png: {img.size}")
    # Also an apple-touch style 180px
    img180 = Image.open(ROOT / "assets" / "Aegis_logo.png").convert("RGBA").resize((180, 180), Image.LANCZOS)
    img180.save(PUB / "apple-touch-icon.png", optimize=True)
    print("apple-touch-icon.png: (180, 180)")


process_web_lockup()
process_favicon()
for f in sorted(PUB.glob("*")):
    print(f"  {f.name}: {f.stat().st_size} bytes")
