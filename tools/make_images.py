r"""Swaps the page's screenshots in one step.

Put your full-resolution captures in img/raw/ named app, video, audio, playlist and welcome (.png, .jpg or .webp), then run

    python tools/make_images.py            (needs Pillow: pip install pillow)

Screenshots of an interface are written LOSSLESS (WebP): no JPEG blur around small text. For each capture it writes
  img/<name>.webp      the capture (or its cropped part) at its own size, never scaled up, 3840 px wide at most: for sharp (2x) screens
  img/<name>-1x.webp   the same scaled down to 1280 px, only when the capture is wider than that: for ordinary screens
and updates every <img data-shot="<name>"> in index.html: the file, its real width and height (so the page does not jump while it loads), and a
srcset with both files, so each screen takes the one it needs. A name with no capture in img/raw/ is left as it is. img/raw/ is not committed
(.gitignore); the generated files are.

Which screenshot is where: app = the app window (the hero, and the pause/resume block, which shows its top left through CSS: class "crop"),
video = the button on a video, audio = an audio page, playlist = the playlist window, welcome = the extension's welcome page.

img/crops.json says which part of a capture is kept, as FRACTIONS (left, top, right, bottom) of the capture, for example {"video": [0.01, 0.25, 0.63, 0.88]};
a name that is not in it is used whole. Cut from the capture's own pixels (never scaled up). The boxes fit THE LAYOUT of a capture: a recapture that is laid
out differently needs new fractions (the tool prints every box in pixels, to check against the picture). A file img/raw/crops.json, if there is one, replaces
entries of the committed one (for trying things without committing them).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image

NAMES = ("app", "video", "audio", "playlist", "welcome")
MAX_WIDTH = 3840
SMALL = 1280
# (the crops live in img/crops.json, which is committed: see the top of this file)
SIZES_HERO = "(min-width: 1128px) 1080px, 100vw"
SIZES_BLOCK = "(min-width: 900px) 640px, 100vw"


def find_raw(raw: Path, name: str) -> Path | None:
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        if (raw / f"{name}{ext}").is_file():
            return raw / f"{name}{ext}"
    return None


def save(image: Image.Image, target: Path, width: int) -> tuple[int, int]:
    """Write `image` lossless, scaled to `width` (never larger than it is); returns the size written."""
    if image.width > width:
        image = image.resize((width, round(image.height * width / image.width)), Image.LANCZOS)
    image.save(target, format="WEBP", lossless=True, quality=100, method=6)  # (lossless: "quality" is only how hard it tries to be small)
    return image.size


def retag(html: str, name: str, big: tuple[int, int], small: tuple[int, int] | None) -> tuple[str, int]:
    pattern = re.compile(rf'<img\b[^>]*\bdata-shot="{name}"[^>]*>')

    def one(match: re.Match) -> str:
        tag = match.group(0)
        hero = " data-hero" in tag
        for attribute in ("src", "srcset", "sizes", "width", "height"):
            tag = re.sub(rf'\s{attribute}="[^"]*"', "", tag)
        extra = f' src="img/{name}.webp" width="{big[0]}" height="{big[1]}"'
        if small is not None:
            extra += f' srcset="img/{name}-1x.webp {small[0]}w, img/{name}.webp {big[0]}w" sizes="{SIZES_HERO if hero else SIZES_BLOCK}"'
        return tag.replace(f'data-shot="{name}"', f'data-shot="{name}"{extra}', 1)

    return pattern.subn(one, html)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=Path(__file__).resolve().parents[1], help="the site folder (default: this one)")
    args = parser.parse_args()
    site = args.site
    page = site / "index.html"
    html = page.read_text(encoding="utf-8")
    crops: dict[str, tuple] = {}
    for where in (site / "img" / "crops.json", site / "img" / "raw" / "crops.json"):  # (the committed file, then a private one in raw/ that replaces it)
        if where.is_file():
            crops.update({k: tuple(v) for k, v in json.loads(where.read_text(encoding="utf-8")).items()})
    done = 0
    for name in NAMES:
        source = find_raw(site / "img" / "raw", name)
        if source is None:
            print(f"{name}: no capture in img/raw/, left as it is")
            continue
        image = Image.open(source).convert("RGB")
        note = ""
        if name in crops:
            left, top, right, bottom = crops[name]
            box = (round(left * image.width), round(top * image.height), round(right * image.width), round(bottom * image.height))
            note = f" (crop {box[0]},{box[1]} to {box[2]},{box[3]} of {image.width}x{image.height})"
            image = image.crop(box)
        big = save(image, site / "img" / f"{name}.webp", MAX_WIDTH)
        small = save(image, site / "img" / f"{name}-1x.webp", SMALL) if image.width > SMALL else None
        if small is None:
            (site / "img" / f"{name}-1x.webp").unlink(missing_ok=True)
        for old in (f"{name}.jpg", f"{name}-1280.jpg"):  # (the JPEGs of before)
            (site / "img" / old).unlink(missing_ok=True)
        html, count = retag(html, name, big, small)
        size = (site / "img" / f"{name}.webp").stat().st_size // 1024
        print(f"{name}: {big[0]}x{big[1]}{note}" + (f" + {small[0]}x{small[1]}" if small else "") + f", {size} KB, {count} <img> updated")
        done += 1
    page.write_text(html, encoding="utf-8")
    print(f"{done} of {len(NAMES)} screenshots swapped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
