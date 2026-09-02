"""Process Aegis.png for README - scale down and optimize."""
from PIL import Image
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUB = ROOT / "dashboard" / "public"

def process_readme_logo():
    """Aegis.png: scale down for README (max width ~200px)."""
    img = Image.open(ROOT / "assets" / "Aegis.jpg").convert("RGBA")
    # Scale down to reasonable README size (max width 200px)
    max_width = 200
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    img.save(ROOT / "assets" / "Aegis_readme.png", optimize=True)
    print(f"Aegis_readme.png: {img.size}")

if __name__ == "__main__":
    process_readme_logo()