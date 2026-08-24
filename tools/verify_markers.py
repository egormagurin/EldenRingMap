"""Render markers onto the extracted master image to eyeball the coordinate affine.

If the affine is right, named graces land exactly on their landmarks.
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw
Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "cache")

COLORS = {"grace": (255, 215, 90), "boss": (235, 80, 80),
          "poi": (120, 200, 255), "region": (170, 170, 170)}


def main():
    master = sys.argv[1] if len(sys.argv) > 1 else "M00"
    data = json.load(open(os.path.join(ROOT, "data", "markers.json"), encoding="utf-8"))
    ms = [m for m in data["markers"] if m.get("master") == master and m.get("px") is not None]
    print(f"{master}: {len(ms)} placed markers")

    img = Image.open(os.path.join(CACHE, f"master_{master}.png")).convert("RGB")
    d = ImageDraw.Draw(img)
    for m in ms:
        x, y = m["px"], m["py"]
        c = COLORS.get(m["cat"], (255, 255, 255))
        r = 22 if m["cat"] in ("grace", "boss") else 12
        d.ellipse([x - r, y - r, x + r, y + r], outline=c, width=6)
        d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=c)

    img.thumbnail((1100, 1100), Image.LANCZOS)
    out = os.path.join(CACHE, f"verify_{master}.png")
    img.save(out)
    print("->", out)

    # A few well-known graces, for a spot check against the real map.
    known = ["The First Step", "Church of Elleh", "Gatefront", "Stormhill Shack",
             "Agheel Lake North", "Third Church of Marika", "Bestial Sanctum",
             "Grand Lift of Dectus", "Roundtable Hold"]
    print("\nlandmark spot check:")
    for k in known:
        for m in ms:
            if m.get("names", {}).get("en") == k:
                ru = m.get("names", {}).get("ru", "")
                print(f"   {k:<26} ({m['px']:7.0f}, {m['py']:7.0f})  {m['map']:<17}{ru}")
                break


if __name__ == "__main__":
    main()
