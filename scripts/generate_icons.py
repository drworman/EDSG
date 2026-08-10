#!/usr/bin/env python3
"""Generate the EDSG icon set.

Run from the repository root:

    python scripts/generate_icons.py

The artwork is generated rather than checked in as opaque binaries so it
can be regenerated at any size, recoloured without a graphics editor, and
reviewed as a diff. Everything under ``images/`` and
``packaging/icons/`` is produced by this script.

Design
------
EDSG shares a visual family with ED Linux Dash: a circular sensor scope
on near-black, concentric range rings, a segmented outer ring broken by
crosshair ticks at the cardinal points, and a glowing core.

What makes it EDSG rather than EDLD is the centre. Where EDLD shows a
single hexagon around one contact, EDSG shows **three hexagonal nodes in
a triangle** — the squad — linked to each other and converging on a
bright central objective: the goal.

Everything is drawn at a supersampled resolution and reduced with a
Lanczos filter, which is cheaper than implementing antialiasing and
gives cleaner curves than PIL's own.
"""

from __future__ import annotations

import math
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = ROOT / "images"
ICONS_DIR = ROOT / "packaging" / "icons"

#: Drawing happens at this multiple of the target size, then downsamples.
SUPERSAMPLE = 4

#: Ceiling on the working canvas edge, in pixels. A 4096 px master at the
#: full supersample would need a 16384 px canvas, which is about a
#: gigabyte per RGBA layer and gets the process killed. Large targets
#: fall back to a smaller multiplier, where the shapes are big enough
#: that the difference is invisible.
MAX_CANVAS = 8192

#: Accent colours. The default is orange to match the application theme;
#: the rest mirror the palette ED Linux Dash offers.
PALETTE: dict[str, tuple[int, int, int]] = {
    "orange": (255, 122, 26),
    "green": (46, 204, 113),
    "blue": (74, 158, 221),
    "purple": (155, 108, 216),
    "red": (224, 90, 82),
    "yellow": (224, 180, 58),
    "light": (208, 216, 224),
}

#: The variant written as the unsuffixed default.
DEFAULT_VARIANT = "orange"

BACKDROP = (11, 14, 18)

#: Sizes packed into the Windows .ico.
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

#: (OSType, pixel size) pairs written into the macOS .icns.
ICNS_ENTRIES = (
    (b"icp4", 16),
    (b"icp5", 32),
    (b"icp6", 64),
    (b"ic07", 128),
    (b"ic08", 256),
    (b"ic09", 512),
    (b"ic10", 1024),
)


def _blend(
    base: tuple[int, int, int], other: tuple[int, int, int], amount: float
) -> tuple[int, int, int]:
    """Mix two colours; ``amount`` of 0 returns ``base``."""
    return tuple(  # type: ignore[return-value]
        round(a + (b - a) * amount) for a, b in zip(base, other, strict=True)
    )


def _hexagon(centre: tuple[float, float], radius: float, rotation: float = 0.0):
    """Return the six vertices of a regular hexagon."""
    cx, cy = centre
    return [
        (
            cx + radius * math.cos(rotation + math.pi / 3 * index),
            cy + radius * math.sin(rotation + math.pi / 3 * index),
        )
        for index in range(6)
    ]


def _overlay(scale: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Return a fresh transparent layer and a draw handle for it."""
    layer = Image.new("RGBA", (scale, scale), (0, 0, 0, 0))
    return layer, ImageDraw.Draw(layer)


def _merge(canvas: Image.Image, layer: Image.Image, opacity: float) -> None:
    """Composite ``layer`` onto ``canvas`` at ``opacity``.

    Translucent detail must be drawn opaque on a separate layer and
    merged like this. Drawing it straight onto the canvas with a low
    alpha does not blend — PIL replaces the pixel outright, which
    punches a transparent hole through everything beneath it.
    """
    if opacity < 1.0:
        layer.putalpha(
            layer.getchannel("A").point(lambda value: round(value * opacity))
        )
    canvas.alpha_composite(layer)


def _soft_disc(
    size: int,
    centre: float,
    radius: float,
    colour: tuple[int, int, int],
    alpha: int,
    blur: float,
) -> Image.Image:
    """Return a blurred disc on its own layer.

    Glows are built this way rather than by stacking translucent circles
    onto the canvas: stacked alpha accumulates toward opaque and blows
    out everything underneath it.
    """
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(
        [centre - radius, centre - radius, centre + radius, centre + radius],
        fill=(*colour, alpha),
    )
    return layer.filter(ImageFilter.GaussianBlur(blur))


def render(size: int, accent: tuple[int, int, int]) -> Image.Image:
    """Render the avatar at ``size`` pixels square."""
    supersample = max(1, min(SUPERSAMPLE, MAX_CANVAS // size))
    scale = size * supersample
    canvas = Image.new("RGBA", (scale, scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    centre = scale / 2
    radius = scale * 0.485

    # Detail is dropped as the target size falls. At 16 px the range
    # rings and link lines are thinner than a pixel and merge into a
    # smear, so below the thresholds the icon becomes a bold ring, three
    # contacts and an objective — which still reads as EDSG.
    show_rings = size >= 64
    show_stubs = size >= 96
    show_links = size >= 32
    solid_nodes = size < 32

    # Strokes are proportionally heavier on small icons so they survive.
    weight = 0.0055 if size >= 64 else (0.0075 if size >= 32 else 0.011)
    line = max(1.0, scale * weight)

    def circle(target: ImageDraw.ImageDraw, r: float, **kwargs) -> None:
        target.ellipse([centre - r, centre - r, centre + r, centre + r], **kwargs)

    # -- body ---------------------------------------------------------
    circle(draw, radius, fill=BACKDROP)

    # A broad, very faint wash so the disc is not flat black. Skipped on
    # tiny icons, where a blur spanning whole pixels just reads as dirt.
    if not solid_nodes:
        canvas.alpha_composite(
            _soft_disc(scale, centre, radius * 0.62, accent, 26, scale * 0.10)
        )

    # -- range rings and inward ticks ---------------------------------
    detail, detail_draw = _overlay(scale)

    if show_rings:
        for fraction, alpha in ((0.80, 120), (0.62, 100), (0.44, 85)):
            r = radius * fraction
            detail_draw.ellipse(
                [centre - r, centre - r, centre + r, centre + r],
                outline=(*accent, alpha),
                width=max(1, round(line * 0.7)),
            )

    for step in range(4 if show_stubs else 0):
        angle = math.radians(90 * step)
        dx, dy = math.cos(angle), math.sin(angle)
        detail_draw.line(
            [
                (centre + dx * radius * 0.30, centre + dy * radius * 0.30),
                (centre + dx * radius * 0.40, centre + dy * radius * 0.40),
            ],
            fill=(*accent, 170),
            width=max(1, round(line * 0.9)),
        )
    _merge(canvas, detail, 0.55)
    del detail, detail_draw

    # -- cardinal ticks crossing the rim ------------------------------
    for step in range(4):
        angle = math.radians(90 * step)
        dx, dy = math.cos(angle), math.sin(angle)
        draw.line(
            [
                (centre + dx * radius * 0.88, centre + dy * radius * 0.88),
                (centre + dx * radius * 1.00, centre + dy * radius * 1.00),
            ],
            fill=(*accent, 255),
            width=max(1, round(line * 1.2)),
        )

    # -- outer ring, broken at the cardinals --------------------------
    box = [centre - radius, centre - radius, centre + radius, centre + radius]
    gap = 8  # degrees either side of each cardinal point
    for step in range(4):
        draw.arc(
            box,
            90 * step + gap,
            90 * (step + 1) - gap,
            fill=(*accent, 255),
            width=max(2, round(line * 2.1)),
        )

    # -- the squad: three nodes in a triangle -------------------------
    node_orbit = radius * (0.56 if not solid_nodes else 0.60)
    node_radius = radius * 0.150
    nodes = [
        (
            centre + node_orbit * math.cos(math.radians(-90 + 120 * index)),
            centre + node_orbit * math.sin(math.radians(-90 + 120 * index)),
        )
        for index in range(3)
    ]

    # Links first, so the nodes sit on top of them.
    links, links_draw = _overlay(scale)
    for index in range(3 if show_links else 0):
        links_draw.line(
            [nodes[index], nodes[(index + 1) % 3]],
            fill=(*accent, 150),
            width=max(1, round(line * 0.9)),
        )
        links_draw.line(
            [nodes[index], (centre, centre)],
            fill=(*accent, 200),
            width=max(1, round(line * 0.9)),
        )
    _merge(canvas, links, 0.6)
    del links, links_draw

    glow = Image.new("RGBA", (scale, scale), (0, 0, 0, 0))
    for node in nodes if not solid_nodes else []:
        ImageDraw.Draw(glow).ellipse(
            [
                node[0] - node_radius * 1.5,
                node[1] - node_radius * 1.5,
                node[0] + node_radius * 1.5,
                node[1] + node_radius * 1.5,
            ],
            fill=(*accent, 34),
        )
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(scale * 0.018)))
    del glow

    for node in nodes:
        if solid_nodes:
            # A filled dot survives where a hexagon outline would not.
            draw.ellipse(
                [
                    node[0] - node_radius * 0.82,
                    node[1] - node_radius * 0.82,
                    node[0] + node_radius * 0.82,
                    node[1] + node_radius * 0.82,
                ],
                fill=(*accent, 255),
            )
            continue
        points = _hexagon(node, node_radius, rotation=math.pi / 2)
        draw.polygon(points, fill=(*_blend(BACKDROP, accent, 0.16), 255))
        draw.polygon(points, outline=(*accent, 255), width=max(1, round(line * 1.4)))

    # -- the goal: a bright objective at the centre -------------------
    core = radius * (0.135 if not solid_nodes else 0.17)
    if not solid_nodes:
        canvas.alpha_composite(
            _soft_disc(scale, centre, core * 2.6, accent, 60, scale * 0.028)
        )
    if solid_nodes:
        circle(draw, core, fill=(*_blend(accent, (255, 255, 255), 0.45), 255))
    else:
        circle(draw, core, fill=(*_blend(BACKDROP, accent, 0.30), 255))
        circle(draw, core, outline=(*accent, 255), width=max(1, round(line * 1.3)))
        circle(draw, core * 0.42, fill=(*_blend(accent, (255, 255, 255), 0.55), 255))

    if supersample == 1:
        return canvas
    return canvas.resize((size, size), Image.LANCZOS)


def write_icns(path: Path, accent: tuple[int, int, int]) -> None:
    """Write a macOS .icns containing PNG payloads.

    Built by hand rather than through Pillow's ICNS writer, which is not
    available on every platform. The format is a simple container: an
    8-byte header followed by length-prefixed, type-tagged blocks.
    """
    import io

    blocks = bytearray()
    for ostype, size in ICNS_ENTRIES:
        buffer = io.BytesIO()
        render(size, accent).save(buffer, format="PNG")
        payload = buffer.getvalue()
        blocks += ostype + struct.pack(">I", len(payload) + 8) + payload

    path.write_bytes(b"icns" + struct.pack(">I", len(blocks) + 8) + bytes(blocks))


def main() -> int:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for name, accent in PALETTE.items():
        for size in (512, 4096):
            suffix = "" if name == DEFAULT_VARIANT else f"_{name}"
            target = IMAGES_DIR / f"edsg_avatar{suffix}_{size}.png"
            render(size, accent).save(target, format="PNG", optimize=True)
            written.append(target)

    accent = PALETTE[DEFAULT_VARIANT]

    png = ICONS_DIR / "edsg.png"
    render(512, accent).save(png, format="PNG", optimize=True)
    written.append(png)

    ico = ICONS_DIR / "edsg.ico"
    largest = render(max(ICO_SIZES), accent)
    largest.save(ico, format="ICO", sizes=[(s, s) for s in ICO_SIZES])
    written.append(ico)

    icns = ICONS_DIR / "edsg.icns"
    write_icns(icns, accent)
    written.append(icns)

    for path in written:
        print(f"{path.relative_to(ROOT)}  ({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
