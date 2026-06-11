"""Generate soc_monitor.ico from Pillow — run once, outputs to project root."""
from __future__ import annotations

import io
import struct
from pathlib import Path
from PIL import Image, ImageDraw

_BG    = (7,   11,  20,  255)
_FRAME = (28,  39,  64,  255)
_CY    = (34,  225, 255, 255)
_GN    = (61,  220, 132, 255)
_LINE  = (22,  34,  55,  255)


def _glow(draw: ImageDraw.ImageDraw, x0: int, y0: int, x1: int, y1: int,
          color: tuple, spread: int = 3) -> None:
    r, g, b, _ = color
    for i in range(spread, 0, -1):
        alpha = int(80 * (1 - i / spread))
        draw.rectangle([x0 - i, y0 - i, x1 + i, y1 + i], fill=(r, g, b, alpha))
    draw.rectangle([x0, y0, x1, y1], fill=color)


def _make_large(size: int) -> Image.Image:
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    p   = max(2, size // 20)
    bh  = max(3, size // 12)

    d.rectangle([0, 0, size - 1, size - 1], fill=_BG)
    d.rectangle([p, p, size - p - 1, size - p - 1], outline=_FRAME, width=max(1, p // 2))
    d.line([(p * 2, p * 3), (size - p * 2, p * 3)], fill=(34, 225, 255, 40), width=1)

    bw = size - p * 6

    # Bar 1 — session (~60%) cyan
    by1   = size * 13 // 32
    fill1 = int(bw * 0.60)
    d.rectangle([p * 3, by1, p * 3 + bw, by1 + bh], fill=_LINE)
    _glow(d, p * 3, by1, p * 3 + fill1, by1 + bh, _CY, spread=max(2, size // 32))

    # Tick marks above bar 1
    tick_y = by1 - max(2, size // 32)
    for frac in (0.25, 0.5, 0.75, 1.0):
        tx = p * 3 + int(bw * frac)
        d.line([(tx, tick_y), (tx, by1 - 1)], fill=(34, 225, 255, 50), width=1)

    # Bar 2 — weekly (~20%) green
    by2   = size * 19 // 32
    fill2 = int(bw * 0.20)
    d.rectangle([p * 3, by2, p * 3 + bw, by2 + bh], fill=_LINE)
    _glow(d, p * 3, by2, p * 3 + fill2, by2 + bh, _GN, spread=max(2, size // 32))

    # Pulse dot top-right
    dot_r = max(2, size // 20)
    dot_x = size - p * 3 - dot_r
    dot_y = p * 2 + dot_r + 2
    _glow(d, dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r, _CY, spread=dot_r)

    # Bottom accent
    d.line([(p * 3, size - p * 3), (size - p * 3, size - p * 3)],
           fill=(61, 220, 132, 100), width=max(1, p // 2))

    return img


def _make_small(size: int) -> Image.Image:
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    d.rectangle([0, 0, size - 1, size - 1], fill=_BG)

    m  = 1
    bw = size - m * 2
    bh = max(2, size // 6)

    by1   = size * 5 // 16
    fill1 = int(bw * 0.60)
    d.rectangle([m, by1, m + bw - 1, by1 + bh - 1], fill=_LINE)
    d.rectangle([m, by1, m + fill1 - 1, by1 + bh - 1], fill=_CY)

    by2   = size * 10 // 16
    fill2 = int(bw * 0.20)
    d.rectangle([m, by2, m + bw - 1, by2 + bh - 1], fill=_LINE)
    d.rectangle([m, by2, m + fill2 - 1, by2 + bh - 1], fill=_GN)

    return img


def _write_ico(images: list[Image.Image], path: Path) -> None:
    """Write PNG-in-ICO (Vista+) with multiple sizes."""
    pngs: list[bytes] = []
    for img in images:
        buf = io.BytesIO()
        img.convert('RGBA').save(buf, format='PNG')
        pngs.append(buf.getvalue())

    count  = len(images)
    offset = 6 + count * 16   # past header + directory

    header    = struct.pack('<HHH', 0, 1, count)
    directory = b''
    for img, png in zip(images, pngs):
        w, h = img.size
        directory += struct.pack(
            '<BBBBHHII',
            w if w < 256 else 0,   # 0 encodes 256
            h if h < 256 else 0,
            0, 0,                  # color count, reserved
            1, 32,                 # planes, bit depth
            len(png), offset,
        )
        offset += len(png)

    with path.open('wb') as f:
        f.write(header + directory)
        for png in pngs:
            f.write(png)


def main() -> None:
    sizes  = [16, 32, 48, 64, 128, 256]
    images = [_make_small(s) if s <= 32 else _make_large(s) for s in sizes]

    out = Path(__file__).parent / 'soc_monitor.ico'
    _write_ico(images, out)
    print(f'Saved {out}  ({out.stat().st_size:,} bytes, {len(sizes)} sizes: {sizes})')


if __name__ == '__main__':
    main()
