"""Recolor exactly the three left mint pillars of MoreRecords' icon.

This script is deliberately strict and refuses unknown upstream artwork.
It preserves all pixels except the specified opaque mint-colored pixels.
"""

from __future__ import annotations

from collections import Counter
from io import BytesIO
import base64
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image

SOURCE_COLOR = (72, 211, 181, 255)
TARGET_COLOR = (220, 49, 58, 255)
SOURCE = Path("MoreRecords/custom_components/more_records/brand/icon.png")


def mint_runs(img: Image.Image) -> list[tuple[int, int]]:
    """Find substantial non-overlapping mint-colored columns."""
    pixels = img.load()
    width, height = img.size
    counts = [
        sum(pixels[x, y] == SOURCE_COLOR for y in range(height))
        for x in range(width)
    ]
    runs = []
    start = None
    for x, count in enumerate(counts + [0]):
        if count >= 8 and start is None:
            start = x
        if count < 8 and start is not None:
            if x - start >= 5:
                runs.append((start, x - 1))
            start = None
    return runs


def recolor(source: bytes) -> bytes:
    with Image.open(BytesIO(source)) as opened:
        img = opened.convert("RGBA")
    if img.size != (256, 256):
        raise ValueError(f"Unexpected MoreRecords image size: {img.size}")
    all_colors = Counter(img.getdata())
    if SOURCE_COLOR not in all_colors:
        raise ValueError("MoreRecords original mint-colored pillars not found")

    intervals = mint_runs(img)
    print("Mint pillar runs:", intervals)
    print("Upstream mint pixel count:", all_colors[SOURCE_COLOR])
    if len(intervals) != 4:
        raise ValueError("Expected four visually separate mint pillars; refusing approximation")

    to_edit = intervals[:3]
    before = list(img.getdata())
    pixels = img.load()
    changed = 0
    for x0, x1 in to_edit:
        for x in range(x0, x1 + 1):
            for y in range(img.height):
                if pixels[x, y] == SOURCE_COLOR:
                    pixels[x, y] = TARGET_COLOR
                    changed += 1
    if changed < 500:
        raise ValueError("Refusing implausibly small recolor")

    after = list(img.getdata())
    for index, (original, final) in enumerate(zip(before, after, strict=True)):
        x = index % img.width
        if original != final and not (
            original == SOURCE_COLOR
            and final == TARGET_COLOR
            and any(left <= x <= right for left, right in to_edit)
        ):
            raise ValueError("Unexpected pixel edited")

    print(f"Pixels recolored: {changed}")
    print("Original remaining colors:", sorted(Counter(after).items(), key=lambda x: -x[1])[:8])
    out = BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def main() -> None:
    result = recolor(SOURCE.read_bytes())
    icon = Path("less_records_icon_new.png")
    icon.write_bytes(result)
    print(f"Generated {icon}: {len(result)} bytes")
    token = os.environ["GH_TOKEN"]
    repository = os.environ["GH_REPO"]
    payload = json.dumps(
        {
            "content": base64.b64encode(result).decode("ascii"),
            "encoding": "base64",
        }
    ).encode("utf-8")
    request = Request(
        f"https://api.github.com/repos/{repository}/git/blobs",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=30) as response:
        sha = json.load(response)["sha"]
    print("LESSRECORDS_RECOLORED_ICON_BLOB_SHA=" + sha)


if __name__ == "__main__":
    main()
