r"""Swaps the page's screenshots in one step.

Put your full-resolution captures in img/raw/ named app, video, audio and welcome (.png, .jpg or .webp), then run

    python tools/make_images.py            (needs Pillow: pip install pillow)

For each capture it writes img/<name>.jpg at the capture's own size (only ever scaled DOWN, to 2560 px wide at most; nothing is upscaled), and, when
that is wider than 1280 px, img/<name>-1280.jpg for ordinary screens. Then it updates every <img data-shot="<name>"> in index.html: the
file, the real width and height (so the page does not jump while it loads) and a srcset, so each screen takes the smaller or the larger file.
A name with no capture in img/raw/ is left as it is. img/raw/ is not committed (.gitignore); the generated files are.

Which screenshot is where: app = the app window (the hero, and the pause/resume block, a crop of its top left), video = the button on a video,
audio = an audio page, welcome = the extension's welcome page (zoomed in by CSS, the class "zoom" in index.html).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PIL import Image

NAMES = ("app", "video", "audio", "welcome")
MAX_WIDTH = 2560
SMALL = 1280
SIZES_HERO = "(min-width: 1128px) 1080px, 100vw"
SIZES_BLOCK = "(min-width: 900px) 640px, 100vw"


def find_raw(raw: Path, name: str) -> Path | None:
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        if (raw / f"{name}{ext}").is_file():
            return raw / f"{name}{ext}"
    return None


def save(image: Image.Image, target: Path, width: int) -> tuple[int, int]:
    """Write `image` scaled to `width` (never larger than it is) and return the size written."""
    if image.width > width:
        image = image.resize((width, round(image.height * width / image.width)), Image.LANCZOS)
    image.save(target, quality=88, optimize=True, progressive=True)
    return image.size


def retag(html: str, name: str, big: tuple[int, int], small: tuple[int, int] | None) -> tuple[str, int]:
    pattern = re.compile(rf'<img\b[^>]*\bdata-shot="{name}"[^>]*>')

    def one(match: re.Match) -> str:
        tag = match.group(0)
        hero = " data-hero" in tag
        for attribute in ("src", "srcset", "sizes", "width", "height"):
            tag = re.sub(rf'\s{attribute}="[^"]*"', "", tag)
        extra = f' src="img/{name}.jpg" width="{big[0]}" height="{big[1]}"'
        if small is not None:
            extra += f' srcset="img/{name}-{SMALL}.jpg {small[0]}w, img/{name}.jpg {big[0]}w" sizes="{SIZES_HERO if hero else SIZES_BLOCK}"'
        return tag.replace(f'data-shot="{name}"', f'data-shot="{name}"{extra}', 1)

    return pattern.subn(one, html)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=Path(__file__).resolve().parents[1], help="the site folder (default: this one)")
    args = parser.parse_args()
    site = args.site
    page = site / "index.html"
    html = page.read_text(encoding="utf-8")
    done = 0
    for name in NAMES:
        source = find_raw(site / "img" / "raw", name)
        if source is None:
            print(f"{name}: no capture in img/raw/, left as it is")
            continue
        image = Image.open(source).convert("RGB")
        big = save(image, site / "img" / f"{name}.jpg", MAX_WIDTH)
        small = save(image, site / "img" / f"{name}-{SMALL}.jpg", SMALL) if image.width > SMALL else None
        if small is None:
            (site / "img" / f"{name}-{SMALL}.jpg").unlink(missing_ok=True)
        html, count = retag(html, name, big, small)
        print(f"{name}: {image.width}x{image.height} -> {big[0]}x{big[1]}" + (f" + {small[0]}x{small[1]}" if small else "") + f", {count} <img> updated")
        done += 1
    page.write_text(html, encoding="utf-8")
    print(f"{done} of {len(NAMES)} screenshots swapped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
