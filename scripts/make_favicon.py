#!/usr/bin/env python3
"""Render the Gemini-brand favicon SVG into PNG/ICO assets.

Usage:
    scripts/make_favicon.py [--out DIR]

Produces:
    <out>/favicon.ico            (32x32, browser default request)
    <out>/favicon-32.png         (Adaptive-icon / multiple sizes)
    <out>/favicon-128.png
    <out>/gemini-logo.svg        (source asset)

Requires cairosvg (see requirements.txt). Safe to run repeatedly.
"""
import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser(description="Render the Gemini favicon.")
    ap.add_argument("--out", default=None, help="output directory (default: repo root)")
    ap.add_argument("--svg", default="frontend/favicon/gemini-logo.svg")
    args = ap.parse_args()

    out = args.out or os.path.join(REPO_ROOT, "frontend", "favicon")
    os.makedirs(out, exist_ok=True)

    from cairosvg import svg2png

    from PIL import Image

    sizes = [32, 128]
    for size in sizes:
        svg2png(url=args.svg, write_to=os.path.join(out, f"favicon-{size}.png"),
                output_width=size, output_height=size)
        Image.open(os.path.join(out, f"favicon-{size}.png")).convert("RGBA")  # validate
        print(f"wrote {out}/favicon-{size}.png")

    # ICO is 32x32 for modern browsers.
    svg2png(url=args.svg, write_to=os.path.join(out, "favicon.ico"), output_width=32,
            output_height=32)
    print(f"wrote {out}/favicon.ico")


if __name__ == "__main__":
    sys.exit(main())
