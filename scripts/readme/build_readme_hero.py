#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools==4.67.0", "brotli==1.2.0"]
# ///
"""Build the animated README hero, assets/joflux-readme-hero.svg.

The banner follows the soakes/cv README hero, like the netspeedy/s3ctl, zquota and s3mirror ones:
the joflux mark, a two-line headline, a short body and a meta row on the left, and a generated
scene on the right. The scene is a migration run: repos leave a GitHub cluster, cross the five
stage gates (export, migrate, monitor, verify, archive) and land in a Forgejo cluster, shifting
from cyan to amber on the way. Each gate flashes as a repo crosses and writes down to the run's
JSON state, the verify gate carries a tick, and archived originals sit dimmed in the source.

Edit the copy, layout or timing here and run `make readme-hero` rather than editing the generated
SVG. netspeedy/homebrew-joflux shows the same banner, built from a copy of this script in its
.github/scripts, so copy changes there too. The headline is positioned from measured advances
(see ADVANCE); if you change its words, measure them again with measure_headline.py. Inter and
JetBrains Mono (SIL Open Font License 1.1) are the Google Fonts builds, kept on
assets.netspeedy.io and pinned by checksum in FAMILIES. They're subset here to the characters the
finished SVG renders and embedded, so the hero renders the same on every platform, and because
fontTools is pinned too, a rebuild gives the same bytes. It runs under `uv run`, which installs
that fontTools, and the first run needs network access to download the fonts.
"""

from __future__ import annotations

import base64
import hashlib
import io
import math
import os
import random
import shutil
import subprocess
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "assets" / "joflux-readme-hero.svg"
# assets.netspeedy.io's Cloudflare zone turns away urllib's default user agent.
USER_AGENT = "netspeedy-readme-hero"

# The website's blue, cyan and amber (website/style.css) and the favicon's blue-to-amber mark,
# with the same inks as the s3ctl hero so the netspeedy banners read as one family.
BG = "#060B13"
INK = "#F1F5FA"
INK_2 = "#B5C0CD"
INK_3 = "#808D9E"
BLUE = "#18A8FF"
CYAN = "#4BD8FF"
CYAN_2 = "#A8ECFF"
AMBER = "#F5B841"
AMBER_2 = "#FDE1A7"
GREEN = "#38D99F"
STAGES = ["EXPORT", "MIGRATE", "MONITOR", "VERIFY", "ARCHIVE"]

# Fonts: css class -> (source font, its sha256, weight range, embedded family name). The
# sources are the Google Fonts builds of Inter 4.001 and JetBrains Mono 2.211, kept on
# assets.netspeedy.io and cached after the first download. A new version goes up there
# under a new filename, so these files never change.
FONT_HOST = "https://assets.netspeedy.io/versioned/fonts"
FONT_CACHE = Path.home() / ".cache" / "netspeedy-fonts"
FAMILIES = {
    "sans": (
        "inter-opsz-wght.4.001.ttf",
        "29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031",
        "400 800",
        "Hero Sans",
    ),
    "mono": (
        "jetbrains-mono-wght.2.211.ttf",
        "48715a42ec242c21e9f02692891e147d022299a52e48d5e413e1a942193ffeda",
        "400 700",
        "Hero Mono",
    ),
}
FONT_CSS = (
    ".sans{font-family:'Hero Sans',-apple-system,'Segoe UI','Helvetica Neue',Arial,sans-serif;"
    "font-optical-sizing:auto;}"
    ".mono{font-family:'Hero Mono','SF Mono',Menlo,Consolas,monospace;}"
)
TWINKLE_CSS = (
    ".tw{animation:tw 5.2s ease-in-out infinite;transform-box:fill-box;transform-origin:center}"
    ".tw1{animation-duration:6.4s}.tw2{animation-duration:4.6s}.tw3{animation-duration:7.3s}"
    "@keyframes tw{0%,100%{opacity:.85}50%{opacity:.15}}"
)

# Starfield: seeded, so rebuilding gives the same sky. No star sits behind the copy.
STAR_SEED = 11
STARS = 110
TWINKLING = 16
COPY_BOX = (36, 30, 520, 340)

# Headline advances in px, measured by measure_headline.py on Inter 800 at 44px (opsz 32,
# letter-spacing -1.3). The swash and the gradients are placed from these.
ADVANCE = {
    "Move the ": 189.61,
    "whole": 119.94,
    "Move the whole org.": 393.21,
    "Verify every repo.": 343.30,
}


# Fonts


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def font_source(name: str, sha256: str) -> bytes:
    """A pinned source font from FONT_HOST, checked against its sha256 and cached."""
    cached = FONT_CACHE / name
    if cached.exists():
        data = cached.read_bytes()
        if hashlib.sha256(data).hexdigest() == sha256:
            return data
    data = fetch(f"{FONT_HOST}/{name}")
    if hashlib.sha256(data).hexdigest() != sha256:
        raise SystemExit(f"{FONT_HOST}/{name} doesn't match its pinned sha256")
    FONT_CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(data)
    return data


def subset_font(source: bytes, text: str) -> bytes:
    """The variable font cut down to the given characters, as woff2.

    Every axis is kept: trimming them with fontTools' instancer moved the headline's
    pixels. The source's head timestamp is kept too, so the same text always gives the
    same bytes.
    """
    font = TTFont(io.BytesIO(source), recalcTimestamp=False)
    options = subset.Options()
    options.hinting = False
    subsetter = subset.Subsetter(options)
    subsetter.populate(text=text)
    subsetter.subset(font)
    font.flavor = "woff2"
    out = io.BytesIO()
    font.save(out)
    return out.getvalue()


def collect_chars(svg: str) -> dict[str, set[str]]:
    """Characters rendered by each font class, inherited through groups."""
    chars: dict[str, set[str]] = {name: set() for name in FAMILIES}

    def family_of(element: ET.Element, inherited: str | None) -> str | None:
        for cls in (element.get("class") or "").split():
            if cls in FAMILIES:
                return cls
        return inherited

    def walk(element: ET.Element, inherited: str | None, in_text: bool) -> None:
        tag = element.tag.split("}")[-1]
        family = family_of(element, inherited)
        if tag in ("style", "title", "desc", "script"):
            return
        is_text = in_text or tag in ("text", "tspan", "textPath")
        if is_text and tag in ("text", "tspan", "textPath") and element.text:
            if family is None:
                raise SystemExit(f"text without a font class: {element.text!r}")
            chars[family].update(element.text)
        for child in element:
            walk(child, family, is_text)
            if is_text and child.tail and child.tail.strip():
                chars[family or "sans"].update(child.tail)

    walk(ET.fromstring(svg), None, False)
    return chars


def font_faces(svg: str) -> str:
    """One @font-face per family, subset to exactly the characters the SVG renders."""
    chars = collect_chars(svg)
    faces = []
    for cls, (name, sha256, weights, local) in FAMILIES.items():
        used = chars[cls]
        if not used:
            continue
        text = "".join(sorted((used - set("\n\t\r")) | {" "}))
        data = base64.b64encode(subset_font(font_source(name, sha256), text)).decode()
        faces.append(
            f"@font-face{{font-family:'{local}';font-weight:{weights};"
            f"font-style:normal;src:url(data:font/woff2;base64,{data}) "
            "format('woff2');}"
        )
    return "".join(faces)


# Small helpers


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def num(value: float) -> str:
    """One decimal place, without a trailing .0."""
    text = f"{value:.1f}"
    return text[:-2] if text.endswith(".0") else text


def mono_width(chars: int, size: float, spacing: float = 0.0) -> float:
    """JetBrains Mono advances exactly 0.6 em; letter-spacing applies per glyph."""
    return chars * (size * 0.6 + spacing)


def gradient(kind: str, attrs: str, stops: list[tuple[str, str, str]]) -> list[str]:
    lines = [f"    <{kind} {attrs}>"]
    for offset, colour, opacity in stops:
        alpha = f' stop-opacity="{opacity}"' if opacity else ""
        lines.append(f'      <stop offset="{offset}" stop-color="{colour}"{alpha} />')
    return [*lines, f"    </{kind}>"]


def poly(points: list[tuple[float, float]]) -> str:
    return "M" + "L".join(f"{num(x)} {num(y)}" for x, y in points)


def path_length(points: list[tuple[float, float]]) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def cubic_points(p0, p1, p2, p3, steps: int = 80) -> list[tuple[float, float]]:
    pts = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


def chip_width(label: str, size: float = 10.5, spacing: float = 1.2) -> float:
    return mono_width(len(label), size, spacing) - spacing + 16


def chip(x: float, y: float, label: str, colour: str) -> str:
    """A mono label in a small outlined box; (x, y) is the box's top-left corner."""
    width = chip_width(label)
    return (
        f'<g><rect x="{num(x)}" y="{num(y)}" width="{num(width)}" height="20" rx="4" '
        f'fill="#0A0F18" fill-opacity="0.92" stroke="{colour}" stroke-opacity="0.45" />'
        f'<text class="mono" x="{num(x + width / 2)}" y="{num(y + 13.8)}" text-anchor="middle" '
        f'font-size="10.5" letter-spacing="1.2" fill="{colour}">{esc(label)}</text></g>'
    )


def packet(
    d: str,
    length: float,
    colour: str,
    dur: float,
    delay: float,
    rest: float,
    seg: float,
    width: float,
    name: str,
) -> tuple[str, str]:
    """A dash travelling along a path, as (element, keyframes).

    The dash runs from just before the start to just past the end once per cycle. Its
    stroke-dashoffset attribute puts it `rest` of the way along, which is where it sits when
    animation is off.
    """
    keyframes = (
        f"@keyframes {name}{{from{{stroke-dashoffset:{num(seg)}}}"
        f"to{{stroke-dashoffset:{num(-length)}}}}}"
    )
    element = (
        f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{width}" '
        f'stroke-linecap="butt" stroke-dasharray="{num(seg)} {num(length + seg)}" '
        f'stroke-dashoffset="{num(-length * rest)}" '
        f'style="animation:{name} {dur:.2f}s linear infinite;animation-delay:{delay:.2f}s" />'
    )
    return element, keyframes


# Shared card


def starfield(free: list[tuple[float, float, float, float]]) -> tuple[list[str], list[str]]:
    """Background gradient and nebula defs, plus the body: base, glows and seeded stars."""
    rng = random.Random(STAR_SEED)
    stars = []
    tries = 0
    while len(stars) < STARS and tries < STARS * 50:
        tries += 1
        x, y = rng.uniform(8, 1192), rng.uniform(8, 392)
        if any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in free):
            continue
        radius = rng.choice([0.55, 0.6, 0.7, 0.8, 0.9, 1.0, 1.15])
        stars.append((x, y, radius, rng.uniform(0.18, 0.6)))
    twinkling = [
        f'<circle class="tw tw{i % 4}" cx="{num(x)}" cy="{num(y)}" r="{num(r + 0.25)}" '
        f'fill="#DDF2FF" opacity="{o + 0.25:.2f}" '
        f'style="animation-delay:-{rng.uniform(0, 6):.1f}s" />'
        for i, (x, y, r, o) in enumerate(stars[:TWINKLING])
    ]
    plain = "".join(
        f'<circle cx="{num(x)}" cy="{num(y)}" r="{num(r)}" opacity="{o:.2f}" />'
        for x, y, r, o in stars[TWINKLING:]
    )
    defs = [
        '    <linearGradient id="spaceBg" x1="0" y1="0" x2="0.35" y2="1">',
        '      <stop offset="0" stop-color="#081020" />',
        f'      <stop offset="0.55" stop-color="{BG}" />',
        '      <stop offset="1" stop-color="#0B1424" />',
        "    </linearGradient>",
        *gradient(
            "radialGradient",
            'id="nebA" cx="0.5" cy="0.5" r="0.5"',
            [("0", BLUE, "0.3"), ("1", BLUE, "0")],
        ),
        *gradient(
            "radialGradient",
            'id="nebB" cx="0.5" cy="0.5" r="0.5"',
            [("0", "#3B4BB8", "0.3"), ("1", "#3B4BB8", "0")],
        ),
    ]
    body = [
        '    <rect width="1200" height="400" fill="url(#spaceBg)" />',
        '    <ellipse cx="190" cy="-30" rx="520" ry="260" fill="url(#nebB)" />',
        '    <ellipse cx="920" cy="430" rx="560" ry="300" fill="url(#nebA)" opacity="0.5" />',
        f'    <g fill="#CFE6FF">{plain}</g>',
        f'    <g>{"".join(twinkling)}</g>',
    ]
    return defs, body


def mark_symbols() -> list[str]:
    """The joflux mark from website/favicon.svg, without its tile."""
    return [
        *gradient(
            "linearGradient",
            'id="markG" x1="10" y1="8" x2="54" y2="56" gradientUnits="userSpaceOnUse"',
            [("0", BLUE, ""), ("0.56", CYAN, ""), ("1", AMBER, "")],
        ),
        '    <symbol id="mark" viewBox="0 0 64 64">',
        '      <path d="M17 17h28c6 0 11 5 11 11s-5 11-11 11H30c-5 0-9 4-9 9s4 9 9 9h4" '
        'fill="none" stroke="url(#markG)" stroke-width="7" stroke-linecap="round" />',
        '      <path d="M17 28h16c6 0 11 5 11 11S39 50 33 50h-3" fill="none" stroke="#F4F8FF" '
        'stroke-width="7" stroke-linecap="round" opacity="0.9" />',
        "    </symbol>",
    ]


def lockup() -> list[str]:
    return [
        '  <rect x="48.5" y="38.5" width="33" height="33" rx="8" fill="#0F1218" '
        'stroke="#3B4A5F" stroke-width="1.2" />',
        '  <use href="#mark" x="49" y="39" width="32" height="32" />',
        f'  <text class="sans" x="94" y="52.5" font-size="15" font-weight="600" '
        f'fill="{INK}">joflux</text>',
        f'  <text class="sans" x="94" y="69.5" font-size="12" fill="{INK_3}">'
        "netspeedy · GitHub to Forgejo migration</text>",
    ]


def headline(prefix: str, word: str, suffix: str, second: str) -> tuple[list[str], list[str]]:
    """Two lines at 44px: line one with a highlighted word and an amber swash under it."""
    x = 46.0
    first = prefix + word + suffix
    start = x + ADVANCE[prefix]
    end = start + ADVANCE[word.rstrip(",.")]
    defs = [
        *gradient(
            "linearGradient",
            f'id="titleWhite" gradientUnits="userSpaceOnUse" x1="{num(x)}" y1="0" '
            f'x2="{num(x + ADVANCE[first])}" y2="0"',
            [("0", "#FFFFFF", ""), ("1", "#DCE6FF", "")],
        ),
        *gradient(
            "linearGradient",
            f'id="hl" gradientUnits="userSpaceOnUse" x1="{num(start)}" y1="0" '
            f'x2="{num(end)}" y2="0"',
            [("0", CYAN_2, ""), ("0.5", "#F4F7FA", ""), ("1", AMBER, "")],
        ),
        *gradient(
            "linearGradient",
            f'id="titleTwo" gradientUnits="userSpaceOnUse" x1="{num(x)}" y1="0" '
            f'x2="{num(x + ADVANCE[second])}" y2="0"',
            [("0", CYAN_2, ""), ("0.5", CYAN, ""), ("1", AMBER, "")],
        ),
        *gradient(
            "linearGradient",
            'id="uline" x1="0" y1="0" x2="1" y2="0"',
            [("0", AMBER, "0.35"), ("0.5", AMBER, ""), ("1", AMBER, "0.5")],
        ),
    ]
    span = end - start
    els = [
        f'  <text class="sans" x="{num(x)}" y="160" font-size="44" font-weight="800" '
        'letter-spacing="-1.3" xml:space="preserve">'
        f'<tspan fill="url(#titleWhite)">{esc(prefix)}</tspan>'
        f'<tspan fill="url(#hl)">{esc(word)}</tspan>'
        f'<tspan fill="url(#titleWhite)">{esc(suffix)}</tspan></text>',
        f'  <path d="M{num(start + 2)} 172.5q{num(span * 0.5)} -6.5 {num(span - 6)} -1.5" '
        'fill="none" stroke="url(#uline)" stroke-width="2.6" stroke-linecap="round" />',
        f'  <text class="sans" x="{num(x)}" y="212" font-size="44" font-weight="800" '
        f'letter-spacing="-1.3" fill="url(#titleTwo)">{esc(second)}</text>',
    ]
    return defs, els


def body(lines: list[list[tuple[str, bool]]]) -> list[str]:
    out = [f'  <text class="sans" font-size="15.5" fill="{INK_2}" xml:space="preserve">']
    for i, segments in enumerate(lines):
        spans = "".join(
            (
                f'<tspan class="mono" font-size="14" fill="{CYAN_2}">{esc(text)}</tspan>'
                if mono
                else esc(text)
            )
            for text, mono in segments
        )
        out.append(f'    <tspan x="48" y="{254 + 23 * i}">{spans}</tspan>')
    out.append("  </text>")
    return out


def meta_row(labels: list[str]) -> str:
    x = 48.0
    parts = []
    for i, label in enumerate(labels):
        if i:
            parts.append(f'<circle cx="{num(x + 9)}" cy="318.3" r="2.1" fill="{AMBER}" />')
            x += 19
        parts.append(f'<text x="{num(x)}" y="322">{esc(label)}</text>')
        x += mono_width(len(label), 11.5, 1.5)
    return (
        f'  <g class="mono" font-size="11.5" letter-spacing="1.5" fill="{INK_3}">'
        f'{"".join(parts)}</g>'
    )


# Scene: gates


def hex_cluster(cx: float, cy: float, rings: int, pitch: float) -> list[tuple[float, float]]:
    """Hex-packed points around a centre, squashed a little vertically."""
    pts = [(cx, cy)]
    for r in range(1, rings + 1):
        for side in range(6):
            a0 = math.radians(60 * side)
            a1 = math.radians(60 * (side + 1))
            for s in range(r):
                f = s / r
                x = cx + r * pitch * ((1 - f) * math.cos(a0) + f * math.cos(a1))
                y = cy + r * pitch * ((1 - f) * math.sin(a0) + f * math.sin(a1)) * 0.92
                pts.append((x, y))
    return pts


def tile(x: float, y: float, size: float, colour: str, fill_op: float, stroke_op: float) -> str:
    """A repo: a small rounded square centred on (x, y)."""
    return (
        f'<rect x="{num(x - size / 2)}" y="{num(y - size / 2)}" width="{num(size)}" '
        f'height="{num(size)}" rx="{num(size * 0.24)}" fill="{colour}" fill-opacity="{fill_op}" '
        f'stroke="{colour}" stroke-opacity="{stroke_op}" stroke-width="1.2" />'
    )


def scene_gates() -> tuple[list[str], str, str, list[tuple[float, float, float, float]]]:
    """Repos leave a GitHub cluster, cross five stage gates and land in a Forgejo cluster.

    Three tracks run between the clusters with two repos on each, at their own speeds; the
    track's gradient turns each repo from cyan to amber as it goes. Every gate flashes in turn
    and sends a write down to the migration_output chip. Every repo is drawn at a resting point
    along its track for reduced motion.
    """
    css, parts = [], []
    left, right = (660.0, 206.0), (1112.0, 206.0)
    src = hex_cluster(*left, 2, 22)
    dst = hex_cluster(*right, 2, 22)
    for (x, y), colour, halo in ((left, CYAN, "haloL"), (right, AMBER, "haloR")):
        parts.append(
            f'<circle cx="{num(x)}" cy="{num(y)}" r="66" fill="none" stroke="{colour}" '
            'stroke-opacity="0.22" stroke-dasharray="0.01 6" stroke-width="1.6" '
            'stroke-linecap="round" />'
        )
        parts.append(f'<circle cx="{num(x)}" cy="{num(y)}" r="80" fill="url(#{halo})" />')
    # Archived originals are dimmed in the source; slots still waiting are empty outlines.
    for i, (x, y) in enumerate(src):
        archived = i in (3, 8, 12, 15)
        parts.append(tile(x, y, 13, CYAN, 0.08 if archived else 0.2, 0.35 if archived else 0.85))
    for i, (x, y) in enumerate(dst):
        landed = i not in (2, 9, 14, 17)
        parts.append(tile(x, y, 13, AMBER, 0.22 if landed else 0.0, 0.85 if landed else 0.35))

    gates_x = [770 + 66 * i for i in range(5)]
    for i, gx in enumerate(gates_x):
        parts.append(f'<path d="M{gx} 120V292" stroke="url(#gate)" stroke-width="1.4" />')
        parts.append(
            f'<path class="gf" d="M{gx} 120V292" stroke="{AMBER_2 if i < 4 else CYAN_2}" '
            f'stroke-width="2.4" style="animation-delay:{i * 0.42:.2f}s" />'
        )
        parts.append(
            f'<text class="mono" x="{gx}" y="110" text-anchor="middle" font-size="9.5" '
            f'letter-spacing="1.4" fill="{INK_3}">{STAGES[i]}</text>'
        )
        parts.append(
            f'<circle cx="{gx}" cy="306" r="3" fill="{AMBER if i < 4 else CYAN}" '
            'fill-opacity="0.85" />'
        )
    css.append(
        ".gf{opacity:0;animation:gf 2.1s ease-out infinite}"
        "@keyframes gf{0%{opacity:0}6%{opacity:.9}30%{opacity:0}100%{opacity:0}}"
    )

    # Each gate writes down to the run's state.
    label = "migration_output/*.json"
    cw = chip_width(label)
    sx, sy = (gates_x[0] + gates_x[-1]) / 2, 336
    for i, gx in enumerate(gates_x):
        p = cubic_points(
            (gx, 306), (gx, 322), (sx + (gx - sx) * 0.35, 322), (sx + (gx - sx) * 0.3, sy), 20
        )
        d = poly(p)
        parts.append(
            f'<path d="{d}" fill="none" stroke="{INK_3}" stroke-opacity="0.35" '
            'stroke-width="1" />'
        )
        el, kf = packet(d, path_length(p), AMBER_2, 2.1, i * 0.42 - 2.1, 0.5, 4, 2.4, f"wr{i}")
        parts.append(el)
        css.append(kf)
    parts.append(chip(sx - cw / 2, sy, label, CYAN_2))

    # Tracks with repos in flight.
    for k, y in enumerate((180, 206, 232)):
        p = cubic_points(
            (left[0] + 52, y),
            (760, y + (206 - y) * 0.4),
            (1010, y + (206 - y) * 0.4),
            (right[0] - 52, y),
            80,
        )
        d = poly(p)
        length = path_length(p)
        parts.append(
            f'<path d="{d}" fill="none" stroke="url(#track)" stroke-opacity="0.4" '
            'stroke-width="1.2" />'
        )
        for n in range(2):
            el, kf = packet(
                d,
                length,
                "url(#track)",
                4.2 + 0.5 * k,
                -(k * 1.4 + n * 2.1),
                (0.18 + 0.33 * k + 0.4 * n) % 0.95,
                10,
                10,
                f"rp{k}{n}",
            )
            parts.append(el)
            css.append(kf)

    # The verify gate's tick.
    vx = gates_x[3]
    parts.append(
        f'<g class="ok"><circle cx="{vx}" cy="140" r="9" fill="#0A0F18" stroke="{GREEN}" '
        'stroke-width="1.4" />'
        f'<path d="M{vx - 4} 140l3 3 5-6" fill="none" stroke="{GREEN}" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round" /></g>'
    )
    css.append(
        ".ok{animation:ok 2.1s ease-out infinite;animation-delay:1.26s}"
        "@keyframes ok{0%{opacity:.5}8%{opacity:1}40%{opacity:.5}100%{opacity:.5}}"
    )
    labels = (
        f'<text class="mono" x="{num(left[0])}" y="304" text-anchor="middle" font-size="10.5" '
        f'letter-spacing="2" fill="{CYAN}">GITHUB</text>'
        f'<text class="mono" x="{num(right[0])}" y="304" text-anchor="middle" font-size="10.5" '
        f'letter-spacing="2" fill="{AMBER}">FORGEJO</text>'
    )
    defs = [
        *gradient(
            "linearGradient",
            f'id="track" gradientUnits="userSpaceOnUse" x1="{num(left[0] + 52)}" y1="0" '
            f'x2="{num(right[0] - 52)}" y2="0"',
            [("0", CYAN, ""), ("0.55", "#9FE2E8", ""), ("1", AMBER, "")],
        ),
        # Vertical lines have a zero-width box, so the gate gradient is in user space.
        *gradient(
            "linearGradient",
            'id="gate" gradientUnits="userSpaceOnUse" x1="0" y1="120" x2="0" y2="292"',
            [
                ("0", CYAN_2, "0"),
                ("0.3", CYAN_2, "0.45"),
                ("0.7", CYAN_2, "0.45"),
                ("1", CYAN_2, "0"),
            ],
        ),
        *gradient(
            "radialGradient",
            'id="haloL" cx="0.5" cy="0.5" r="0.5"',
            [("0", BLUE, "0.28"), ("1", BLUE, "0")],
        ),
        *gradient(
            "radialGradient",
            'id="haloR" cx="0.5" cy="0.5" r="0.5"',
            [("0", AMBER, "0.22"), ("1", AMBER, "0")],
        ),
        *gradient(
            "radialGradient",
            'id="aura" cx="0.5" cy="0.5" r="0.5"',
            [("0", BLUE, "0.18"), ("1", BLUE, "0")],
        ),
    ]
    scene = (
        '<ellipse cx="886" cy="210" rx="340" ry="200" fill="url(#aura)" />'
        + "".join(parts)
        + labels
    )
    return defs, "".join(css), scene, [(580, 70, 1190, 370)]


# Copy

CARD = {
    "title": "joflux - move the whole org, verify every repo",
    "desc": (
        "Repos leave a GitHub cluster, cross five stage gates and land in a Forgejo cluster, "
        "each gate writing to the run's JSON state."
    ),
    "headline": ("Move the ", "whole", " org.", "Verify every repo."),
    "body": [
        [("GitHub organizations into Forgejo or Codeberg, one", False)],
        [
            ("step at a time. Each step leaves ", False),
            ("JSON", True),
            (" you can inspect.", False),
        ],
    ],
    "meta": ["INSPECT", "RETRY", "VERIFY", "AUDIT"],
    "scene": scene_gates,
}


def build_svg(spec: dict = CARD) -> str:
    scene_defs, scene_css, scene, free = spec["scene"]()
    star_defs, star_body = starfield([COPY_BOX, *free])
    head_defs, head_els = headline(*spec["headline"])
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 400" width="960" height="320" '
        'role="img" aria-labelledby="title desc">',
        f'  <title id="title">{esc(spec["title"])}</title>',
        f'  <desc id="desc">{esc(spec["desc"])}</desc>',
        "",
        "  <defs>",
        "    <style>",
        "      /* Inter and JetBrains Mono, SIL Open Font License 1.1, subset to the glyphs used "
        "here. */",
        "      __FONT_FACES__",
        f"      {FONT_CSS}",
        f"      {TWINKLE_CSS}",
        f"      {scene_css}",
        "      @media (prefers-reduced-motion: reduce){",
        "        *{animation:none !important}",
        "      }",
        "    </style>",
        *star_defs,
        *mark_symbols(),
        *head_defs,
        *scene_defs,
        '    <clipPath id="frame"><rect x="1" y="1" width="1198" height="398" rx="20" />'
        "</clipPath>",
        "  </defs>",
        "",
        '  <g clip-path="url(#frame)">',
        *star_body,
        f"    {scene}",
        "  </g>",
        '  <rect x="0.75" y="0.75" width="1198.5" height="398.5" rx="20" fill="none" '
        'stroke="#1A2638" stroke-width="1.5" />',
        "",
        "  <!-- Left: brand and headline -->",
        *lockup(),
        "",
        *head_els,
        *body(spec["body"]),
        meta_row(spec["meta"]),
        "</svg>",
    ]
    return "\n".join(lines) + "\n"


# Social cards

# Both cards are the hero recomposed and frozen at its rest frame. The website's og:image is
# 1200x630, the size link previews expect, and is only written when the repo has a website.
# The GitHub social preview is 1280x640 and is uploaded by hand under Settings > General >
# Social preview, since GitHub has no API for it.
REPO = "joflux"
OG_CARD = ROOT / "website" / "public" / "og-image"
PREVIEW_CARD = ROOT / "assets" / f"{REPO}-social-preview"
SVG_NS = "http://www.w3.org/2000/svg"
CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
    "chromium-browser",
)


def build_social_svg(hero: str, width: int, height: int) -> str:
    """The hero's copy column on the left and its scene on the right, scaled to fill the card."""
    ET.register_namespace("", SVG_NS)
    root = ET.fromstring(hero)

    def tag(name: str) -> str:
        return f"{{{SVG_NS}}}{name}"

    children = list(root)
    defs = root.find(tag("defs"))
    style = defs.find(tag("style"))
    style.text = (style.text or "") + "  *{animation:none !important}\n    "
    frame = next(c for c in children if c.get("clip-path") == "url(#frame)")
    # Everything after the clipped group, bar the frame's outline, is the copy column.
    copy_els = [
        c
        for c in children[children.index(frame) + 1 :]
        if not (c.tag == tag("rect") and c.get("fill") == "none")
    ]
    background = list(frame)
    nebulae = [c for c in background[1:3] if c.tag == tag("ellipse")]
    scene_els = background[5:]  # after the base, the two nebulae and the two star groups

    wide = width >= 1280
    s_copy, s_scene = (1.2, 1.04) if wide else (1.12, 0.98)
    margin = 60 if wide else 56
    card = ET.Element(
        tag("svg"),
        {
            "viewBox": f"0 0 {width} {height}",
            "width": str(width),
            "height": str(height),
            "role": "img",
            "aria-labelledby": "title desc",
        },
    )
    card.extend([root.find(tag("title")), root.find(tag("desc")), defs])
    ET.SubElement(
        card, tag("rect"), {"width": str(width), "height": str(height), "fill": "url(#spaceBg)"}
    )
    glow = ET.SubElement(
        card, tag("g"), {"transform": f"scale({width / 1200:.4f} {height / 400:.4f})"}
    )
    glow.extend(nebulae)
    rng = random.Random(STAR_SEED)
    stars = ET.SubElement(card, tag("g"), {"fill": "#CFE6FF"})
    placed = 0
    while placed < 150:
        x, y = rng.uniform(6, width - 6), rng.uniform(6, height - 6)
        if 40 <= x <= 680 and 110 <= y <= 530:  # keep the copy column clear
            continue
        placed += 1
        radius = rng.choice([0.6, 0.7, 0.8, 0.9, 1.0, 1.2])
        opacity = f"{rng.uniform(0.2, 0.65):.2f}"
        ET.SubElement(
            stars, tag("circle"), {"cx": num(x), "cy": num(y), "r": num(radius), "opacity": opacity}
        )
    scene_x = width - 12 - 1200 * s_scene
    scene_y = (height - 400 * s_scene) / 2 + 6
    scene = ET.SubElement(
        card, tag("g"), {"transform": f"translate({num(scene_x)} {num(scene_y)}) scale({s_scene})"}
    )
    scene.extend(scene_els)
    copy_x = margin - 46 * s_copy
    copy_y = (height - 300 * s_copy) / 2 - 30 * s_copy - 8
    column = ET.SubElement(
        card, tag("g"), {"transform": f"translate({num(copy_x)} {num(copy_y)}) scale({s_copy})"}
    )
    column.extend(copy_els)
    footer = ET.SubElement(
        card,
        tag("text"),
        {
            "class": "mono",
            "x": str(margin),
            "y": str(height - 44),
            "font-size": "15",
            "letter-spacing": "1.5",
            "fill": "#808D9E",
        },
    )
    footer.text = f"github.com/netspeedy/{REPO}"
    return ET.tostring(card, encoding="unicode") + "\n"


def render_png(svg_path: Path, png_path: Path, width: int, height: int) -> None:
    """Screenshot the card in headless Chrome, which renders the embedded fonts exactly."""
    chrome = os.environ.get("CHROME") or next(
        (c for c in CHROME_CANDIDATES if Path(c).exists() or shutil.which(c)), None
    )
    if not chrome:
        raise SystemExit("the social cards need Chrome or Chromium to render; set CHROME")
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run(
            [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                f"--user-data-dir={profile}",
                f"--window-size={width},{height}",
                f"--screenshot={png_path}",
                svg_path.resolve().as_uri(),
            ],
            check=True,
            capture_output=True,
        )


def write_social_cards(hero: str) -> None:
    cards = [(PREVIEW_CARD, 1280, 640, False)]
    if (ROOT / "website").is_dir():
        cards.insert(0, (OG_CARD, 1200, 630, True))
    for base, width, height, keep_svg in cards:
        svg = build_social_svg(hero, width, height)
        svg = svg.replace("__FONT_FACES__", font_faces(svg))
        ET.fromstring(svg)
        base.parent.mkdir(parents=True, exist_ok=True)
        png = base.with_suffix(".png")
        with tempfile.TemporaryDirectory() as tmp:
            svg_path = base.with_suffix(".svg") if keep_svg else Path(tmp) / "card.svg"
            svg_path.write_text(svg, encoding="utf-8")
            render_png(svg_path, png, width, height)
        print(f"Wrote {png.relative_to(ROOT)} ({width}x{height})")


def main() -> None:
    hero = build_svg()
    svg = hero.replace("__FONT_FACES__", font_faces(hero))
    if "http://" in svg.replace("http://www.w3.org/2000/svg", "") or "https://" in svg:
        raise SystemExit("external reference found in the hero SVG")
    ET.fromstring(svg)  # well-formed, or this raises
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)} ({len(svg.encode()) / 1024:.1f} KiB)")
    write_social_cards(hero)


if __name__ == "__main__":
    main()
