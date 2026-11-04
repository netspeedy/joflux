#!/usr/bin/env python3
"""Build the animated README hero, assets/joflux-readme-hero.svg.

The banner follows the soakes/cv README hero, like the s3ctl and zquota ones: the joflux mark, a
two-line headline, a short body and a meta row on the left, and a generated scene on the right.
The scene is a migration run. The GitHub organization is a cluster of repository nodes on the
left and the Forgejo organization a cluster of slots on the right. Repositories travel between
them through the five stage gates (export, migrate, monitor, verify, archive), and each gate
writes to the state.json checkpoint underneath as they pass.

Edit the copy, layout or timing here and run `make readme-hero` rather than editing the
generated SVG. netspeedy/homebrew-joflux shows the same banner, built from a copy of this script
in its .github/scripts, so copy changes there too. The headline is positioned from measured
advances (see ADVANCE); if you change its words, measure them again with measure_headline.py.
Inter and JetBrains Mono (SIL Open Font License 1.1) are fetched from Google Fonts, subset to the
characters the finished SVG renders, and embedded, so the hero renders the same on every
platform. Needs network access.
"""

from __future__ import annotations

import base64
import math
import random
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "assets" / "joflux-readme-hero.svg"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

# The website's blue, cyan and amber (website/style.css), the colours of the joflux mark, with the
# same inks as the other netspeedy banners. Cyan is the GitHub side and amber the Forgejo side.
BG = "#060B13"
INK = "#F1F5FA"
INK_2 = "#B5C0CD"
INK_3 = "#808D9E"
CYAN = "#4BD8FF"
CYAN_2 = "#A8ECFF"
CYAN_3 = "#18A8FF"
AMBER = "#F5B841"
AMBER_2 = "#FDE1A7"
DIM = "#8FA3B8"

# Fonts: css class -> (Google Fonts family spec, embedded family name).
FAMILIES = {
    "sans": ("Inter:opsz,wght@14..32,400..800", "Hero Sans"),
    "mono": ("JetBrains Mono:wght@400..700", "Hero Mono"),
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
    "No ": 63.17,
    "lost": 73.80,
    "No lost repos.": 266.90,
    "Every stage on record.": 437.74,
}


# Fonts


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


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
    for cls, (spec, local) in FAMILIES.items():
        used = chars[cls]
        if not used:
            continue
        text = "".join(sorted((used - set("\n\t\r")) | {" "}))
        query = urllib.parse.urlencode({"family": spec, "text": text, "display": "block"})
        css = fetch(f"https://fonts.googleapis.com/css2?{query}").decode()
        seen = set()
        # Google serves one variable file covering every weight; embed each file once.
        for weight, url in re.findall(
            r"font-weight:\s*([\d ]+);.*?src:\s*url\(([^)]+)\)", css, re.S
        ):
            if url in seen:
                continue
            seen.add(url)
            data = base64.b64encode(fetch(url)).decode()
            faces.append(
                f"@font-face{{font-family:'{local}';font-weight:{weight.strip()};"
                f"font-style:normal;src:url(data:font/woff2;base64,{data}) format('woff2');}}"
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


def dot_paths(
    points: list[tuple[float, float, int]],
    styles: dict[int, tuple[float, float]],
    colour: str = "#D3E4F4",
) -> str:
    """Dots grouped by band, each band one path of round-capped stubs."""
    paths = []
    for band, (opacity, width) in styles.items():
        pts = sorted(((x, y) for x, y, b in points if b == band), key=lambda p: (round(p[1]), p[0]))
        if not pts:
            continue
        moves = []
        px = py = 0.0
        for x, y in pts:
            # "h.01", not "h0": some renderers drop zero-length subpaths.
            moves.append(f"m{num(x - px)} {num(y - py)}h.01")
            px, py = x + 0.01, y
        paths.append(
            f'<path d="M0 0{"".join(moves)}" fill="none" stroke="{colour}" '
            f'stroke-opacity="{opacity}" stroke-width="{width}" stroke-linecap="round" />'
        )
    return "".join(paths)


def chip_width(label: str, size: float = 10.5, spacing: float = 1.2) -> float:
    return mono_width(len(label), size, spacing) - spacing + 16


def chip(x: float, y: float, label: str, colour: str, cls: str = "") -> str:
    """A mono label in a small outlined box; (x, y) is the box's top-left corner."""
    width = chip_width(label)
    attr = f' class="{cls}"' if cls else ""
    return (
        f'<g{attr}><rect x="{num(x)}" y="{num(y)}" width="{num(width)}" height="20" rx="4" '
        f'fill="#0A0F18" fill-opacity="0.9" stroke="{colour}" stroke-opacity="0.4" />'
        f'<text class="mono" x="{num(x + width / 2)}" y="{num(y + 13.8)}" text-anchor="middle" '
        f'font-size="10.5" letter-spacing="1.2" fill="{colour}">{esc(label)}</text></g>'
    )


def cubic_points(p0, p1, p2, p3, steps: int = 80) -> list[tuple[float, float]]:
    pts = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


def path_length(points: list[tuple[float, float]]) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


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
            'id="nebCyan" cx="0.5" cy="0.5" r="0.5"',
            [("0", CYAN_3, "0.3"), ("1", CYAN_3, "0")],
        ),
        *gradient(
            "radialGradient",
            'id="nebAmber" cx="0.5" cy="0.5" r="0.5"',
            [("0", AMBER, "0.16"), ("1", AMBER, "0")],
        ),
        *gradient(
            "radialGradient",
            'id="nebIndigo" cx="0.5" cy="0.5" r="0.5"',
            [("0", "#3B4BB8", "0.3"), ("1", "#3B4BB8", "0")],
        ),
    ]
    body = [
        '    <rect width="1200" height="400" fill="url(#spaceBg)" />',
        '    <ellipse cx="190" cy="-30" rx="520" ry="260" fill="url(#nebIndigo)" />',
        '    <ellipse cx="700" cy="430" rx="460" ry="260" fill="url(#nebCyan)" opacity="0.6" />',
        '    <ellipse cx="1120" cy="420" rx="380" ry="240" fill="url(#nebAmber)" />',
        f'    <g fill="#CFE6FF">{plain}</g>',
        f'    <g>{"".join(twinkling)}</g>',
    ]
    return defs, body


def mark_symbols() -> list[str]:
    """The joflux mark from website/favicon.svg, without its tile."""
    return [
        *gradient(
            "linearGradient",
            'id="markStroke" x1="10" y1="8" x2="54" y2="56" gradientUnits="userSpaceOnUse"',
            [("0", CYAN_3, ""), ("0.56", CYAN, ""), ("1", AMBER, "")],
        ),
        '    <symbol id="mark" viewBox="0 0 64 64">',
        '      <path d="M17 17h28c6 0 11 5 11 11s-5 11-11 11H30c-5 0-9 4-9 9s4 9 9 9h4" fill="none" '
        'stroke="url(#markStroke)" stroke-width="7" stroke-linecap="round" />',
        '      <path d="M17 28h16c6 0 11 5 11 11S39 50 33 50h-3" fill="none" stroke="#F4F8FF" '
        'stroke-width="7" stroke-linecap="round" opacity="0.9" />',
        "    </symbol>",
    ]


def lockup() -> list[str]:
    return [
        '  <rect x="48.5" y="38.5" width="33" height="33" rx="8" fill="#0F1218" stroke="#3B4A5F" '
        'stroke-width="1.2" />',
        '  <use href="#mark" x="49" y="39" width="32" height="32" />',
        f'  <text class="sans" x="94" y="52.5" font-size="15" font-weight="600" fill="{INK}">'
        "joflux</text>",
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
            [("0", "#FFFFFF", ""), ("1", "#D5ECF8", "")],
        ),
        *gradient(
            "linearGradient",
            f'id="hl" gradientUnits="userSpaceOnUse" x1="{num(start)}" y1="0" '
            f'x2="{num(end)}" y2="0"',
            [("0", CYAN_2, ""), ("0.5", "#F4F7FA", ""), ("1", AMBER, "")],
        ),
        *gradient(
            "linearGradient",
            f'id="titleMark" gradientUnits="userSpaceOnUse" x1="{num(x)}" y1="0" '
            f'x2="{num(x + ADVANCE[second])}" y2="0"',
            [("0", CYAN_3, ""), ("0.55", CYAN, ""), ("1", AMBER, "")],
        ),
        *gradient(
            "linearGradient",
            'id="uline" x1="0" y1="0" x2="1" y2="0"',
            [("0", AMBER, "0.35"), ("0.5", AMBER, ""), ("1", AMBER, "0.5")],
        ),
    ]
    span = end - start
    tail = f'<tspan fill="url(#titleWhite)">{esc(suffix)}</tspan>' if suffix else ""
    els = [
        f'  <text class="sans" x="{num(x)}" y="160" font-size="44" font-weight="800" '
        'letter-spacing="-1.3" xml:space="preserve">'
        f'<tspan fill="url(#titleWhite)">{esc(prefix)}</tspan>'
        f'<tspan fill="url(#hl)">{esc(word)}</tspan>{tail}</text>',
        f'  <path d="M{num(start + 2)} 172.5q{num(span * 0.5)} -6.5 {num(span - 6)} -1.5" '
        'fill="none" stroke="url(#uline)" stroke-width="2.6" stroke-linecap="round" />',
        f'  <text class="sans" x="{num(x)}" y="212" font-size="44" font-weight="800" '
        f'letter-spacing="-1.3" fill="url(#titleMark)">{esc(second)}</text>',
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


# Scene: migration run


SRC_CX, DST_CX, CLUSTER_CY = 648.0, 1108.0, 206.0
NODE_PITCH = 27.0  # distance between neighbouring repository nodes
GATES = ["EXPORT", "MIGRATE", "MONITOR", "VERIFY", "ARCHIVE"]
GATE_X0, GATE_STEP = 758.0, 62.0
GATE_TOP, GATE_BOTTOM = 126.0, 280.0
STATE_Y = 316.0  # top of the state.json chip
MIGRATED = 13  # destination slots already filled in the rest frame


def hex_cluster(cx: float, cy: float) -> list[tuple[float, float]]:
    """Nineteen nodes on a hexagon of radius two, ordered from the centre outwards."""
    nodes = []
    for q in range(-2, 3):
        for r in range(-2, 3):
            s = -q - r
            if max(abs(q), abs(r), abs(s)) > 2:
                continue
            x = cx + NODE_PITCH * (q + r / 2)
            y = cy + NODE_PITCH * r * math.sqrt(3) / 2
            nodes.append((max(abs(q), abs(r), abs(s)), x, y))
    nodes.sort(key=lambda n: (n[0], math.atan2(n[2] - cy, n[1] - cx)))
    return [(x, y) for _, x, y in nodes]


def cluster_links(nodes: list[tuple[float, float]], colour: str, opacity: float) -> str:
    """Faint constellation lines between neighbouring nodes."""
    segs = []
    for i, a in enumerate(nodes):
        for b in nodes[i + 1 :]:
            if math.dist(a, b) < NODE_PITCH * 1.05:
                segs.append(f"M{num(a[0])} {num(a[1])}L{num(b[0])} {num(b[1])}")
    return (
        f'<path d="{"".join(segs)}" fill="none" stroke="{colour}" stroke-opacity="{opacity}" '
        'stroke-width="1" />'
    )


def halo(cx: float, cy: float, colour: str) -> str:
    """Two dotted rings round a cluster, brighter on the side facing the gates."""
    points = []
    facing = 1 if cx < 900 else -1
    for ring, r in enumerate((76.0, 87.0)):
        count = int(2 * math.pi * r / 8.5)
        for q in range(count):
            a = 2 * math.pi * (q + ring * 0.5) / count
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            lean = math.cos(a) * facing
            points.append((x, y, 0 if lean < -0.2 else 1 if lean < 0.5 else 2))
    return dot_paths(points, {0: (0.18, 1.2), 1: (0.32, 1.35), 2: (0.5, 1.5)}, colour)


def scene_migration() -> tuple[list[str], str, str, list[tuple[float, float, float, float]]]:
    """Repositories cross five stage gates from a GitHub cluster to a Forgejo cluster."""
    loop = 6.0
    travel = 3.6  # seconds for the lead repository to cross from cluster to cluster
    src_nodes = hex_cluster(SRC_CX, CLUSTER_CY)
    dst_nodes = hex_cluster(DST_CX, CLUSTER_CY)
    x_start, x_end = SRC_CX + 72, DST_CX - 72

    # The two clusters. Archived originals dim on the GitHub side as their copies land.
    archived = set(range(len(src_nodes) - MIGRATED + 1, len(src_nodes)))
    src = []
    for i, (x, y) in enumerate(src_nodes):
        if i in archived:
            src.append(
                f'<circle cx="{num(x)}" cy="{num(y)}" r="7.2" fill="{DIM}" fill-opacity="0.12" '
                f'stroke="{DIM}" stroke-opacity="0.45" stroke-width="1.2" />'
            )
        else:
            src.append(
                f'<circle cx="{num(x)}" cy="{num(y)}" r="7.2" fill="{CYAN}" fill-opacity="0.25" '
                f'stroke="{CYAN}" stroke-width="1.4" />'
            )
    # The next original to be archived dims when the lead repository passes the archive gate.
    nxt = len(src_nodes) - MIGRATED
    ax, ay = src_nodes[nxt]
    archive_at = travel * (GATE_X0 + 4 * GATE_STEP - x_start) / (x_end - x_start)
    src.append(
        f'<circle class="ar" cx="{num(ax)}" cy="{num(ay)}" r="7.2" fill="#142131" '
        f'stroke="{DIM}" stroke-opacity="0.45" stroke-width="1.2" '
        f'style="animation-delay:{archive_at - loop:.2f}s" />'
    )

    dst = []
    for i, (x, y) in enumerate(dst_nodes):
        if i < MIGRATED:
            dst.append(
                f'<circle cx="{num(x)}" cy="{num(y)}" r="7.2" fill="{AMBER}" fill-opacity="0.25" '
                f'stroke="{AMBER}" stroke-width="1.4" />'
            )
        else:
            dst.append(
                f'<circle cx="{num(x)}" cy="{num(y)}" r="7.2" fill="none" stroke="{AMBER}" '
                'stroke-opacity="0.38" stroke-width="1.1" stroke-dasharray="2.4 2.4" />'
            )
    lx, ly = dst_nodes[MIGRATED]
    dst.append(
        f'<circle class="ld" cx="{num(lx)}" cy="{num(ly)}" r="7.2" fill="{AMBER}" '
        f'fill-opacity="0.25" stroke="{AMBER}" stroke-width="1.4" '
        f'style="animation-delay:{travel - loop:.2f}s" />'
    )

    # Three tracks through the gates; the dash takes the cyan-to-amber gradient as it travels.
    css = []
    tracks = []
    packets = []
    for k, (y_end, lead) in enumerate(((186.0, 0.9), (212.0, 0.0), (238.0, 1.9))):
        p0 = (x_start - 6, y_end)
        p3 = (x_end + 6, y_end)
        bend = CLUSTER_CY + (y_end - CLUSTER_CY) * 0.55
        p1, p2 = (x_start + 70, bend), (x_end - 70, bend)
        pts = cubic_points(p0, p1, p2, p3)
        length = path_length(pts)
        d = (
            f"M{num(p0[0])} {num(p0[1])}C{num(p1[0])} {num(p1[1])} {num(p2[0])} {num(p2[1])} "
            f"{num(p3[0])} {num(p3[1])}"
        )
        tracks.append(
            f'<path d="{d}" fill="none" stroke="url(#trackGrad)" stroke-opacity="0.45" '
            'stroke-width="1.2" stroke-dasharray="2 5" />'
        )
        seg = 12
        css.append(
            f"@keyframes pk{k}{{0%{{stroke-dashoffset:{seg}}}"
            f"{travel / loop * 100:.1f}%{{stroke-dashoffset:{num(-length)}}}"
            f"100%{{stroke-dashoffset:{num(-length)}}}}}"
        )
        # The lead repository on each track, then a second one half a loop behind it.
        for j, offset in enumerate((0.0, loop / 2)):
            rest = -length * (0.62, 0.38, 0.18)[k] if j == 0 else seg
            packets.append(
                f'<path d="{d}" fill="none" stroke="url(#trackGrad)" stroke-width="8" '
                f'stroke-dasharray="{seg} {num(length + seg)}" stroke-dashoffset="{num(rest)}" '
                f'style="animation:pk{k} {loop}s linear infinite;'
                f'animation-delay:{lead + offset - loop:.2f}s" />'
            )

    # Gates, each flashing as the lead repository crosses it and writing to state.json.
    gates = []
    writes = []
    state_cx = (GATE_X0 + GATE_X0 + 4 * GATE_STEP) / 2
    for i, label in enumerate(GATES):
        gx = GATE_X0 + i * GATE_STEP
        at = travel * (gx - x_start) / (x_end - x_start)
        delay = f"{at - loop:.2f}s"
        colour = AMBER_2 if i == len(GATES) - 1 else CYAN_2
        gates.append(
            f'<path d="M{num(gx)} {num(GATE_TOP + 12)}V{num(GATE_BOTTOM)}" '
            'stroke="url(#gateGrad)" stroke-width="1.4" />'
            f'<g class="gt" style="animation-delay:{delay}">'
            f'<path d="M{num(gx)} {num(GATE_TOP + 12)}V{num(GATE_BOTTOM)}" stroke="{colour}" '
            'stroke-width="2" />'
            f'<circle cx="{num(gx)}" cy="{num(GATE_TOP)}" r="13" fill="url(#gateGlow)" /></g>'
            f'<circle cx="{num(gx)}" cy="{num(GATE_TOP)}" r="9" fill="#0A0F18" stroke="{colour}" '
            'stroke-width="1.3" />'
            f'<text class="mono" x="{num(gx)}" y="{num(GATE_TOP + 3.6)}" text-anchor="middle" '
            f'font-size="10" font-weight="700" fill="{colour}">{i + 1}</text>'
            f'<text class="mono" x="{num(gx + 0.5)}" y="{num(GATE_TOP - 20)}" text-anchor="middle" '
            f'font-size="9.5" letter-spacing="1" fill="{INK_3}">{label}</text>'
        )
        # A leader from the foot of the gate down to the state.json chip.
        tx = state_cx + (i - 2) * 9
        d = (
            f"M{num(gx)} {num(GATE_BOTTOM + 2)}C{num(gx)} {num(STATE_Y - 14)} {num(tx)} "
            f"{num(GATE_BOTTOM + 18)} {num(tx)} {num(STATE_Y - 1)}"
        )
        pts = cubic_points(
            (gx, GATE_BOTTOM + 2), (gx, STATE_Y - 14), (tx, GATE_BOTTOM + 18), (tx, STATE_Y - 1)
        )
        length = path_length(pts)
        writes.append(
            f'<path d="{d}" fill="none" stroke="{INK_3}" stroke-opacity="0.4" stroke-width="1" '
            'stroke-dasharray="2 4" />'
            f'<path class="wr" d="{d}" fill="none" stroke="{colour}" stroke-width="1.6" '
            f'stroke-dasharray="7 {num(length + 7)}" stroke-dashoffset="7" '
            f'style="animation-name:wr{i};animation-delay:{delay}" />'
        )
        css.append(
            f"@keyframes wr{i}{{0%{{opacity:1;stroke-dashoffset:7}}10%{{opacity:1;"
            f"stroke-dashoffset:{num(-length)}}}11%{{opacity:0}}100%{{opacity:0}}}}"
        )
    css.append(
        f".gt{{opacity:0;animation:gt {loop}s ease-out infinite}}"
        "@keyframes gt{0%{opacity:1}12%{opacity:0}100%{opacity:0}}"
        f".wr{{opacity:0;animation-duration:{loop}s;animation-timing-function:ease-in;"
        "animation-iteration-count:infinite}"
        f".ar{{opacity:0;animation:ar {loop}s ease-out infinite}}"
        "@keyframes ar{0%{opacity:0}8%{opacity:1}"
        f"{(loop - travel) / loop * 100 - 2:.1f}%{{opacity:1}}"
        f"{(loop - travel) / loop * 100:.1f}%{{opacity:0}}100%{{opacity:0}}}}"
        f".ld{{opacity:0;animation:ld {loop}s ease-out infinite;transform-box:fill-box;"
        "transform-origin:center}"
        "@keyframes ld{0%{opacity:0;transform:scale(.4)}6%{opacity:1;transform:scale(1.3)}"
        "12%{transform:scale(1)}88%{opacity:1}96%{opacity:0}100%{opacity:0}}"
        f".st{{animation:st {loop / len(GATES)}s ease-out infinite}}"
        "@keyframes st{0%,100%{opacity:.75}30%{opacity:1}}"
    )

    state_w = chip_width("state.json")
    state = (
        f'<rect x="{num(state_cx - state_w / 2 - 4)}" y="{num(STATE_Y - 4)}" '
        f'width="{num(state_w + 8)}" height="28" rx="8" fill="url(#stateGlow)" class="st" />'
        + chip(state_cx - state_w / 2, STATE_Y, "state.json", INK)
    )
    labels = (
        f'<text class="mono" x="{num(SRC_CX)}" y="{num(CLUSTER_CY + 110)}" text-anchor="middle" '
        f'font-size="10.5" letter-spacing="2" fill="{CYAN}">GITHUB ORG</text>'
        f'<text class="mono" x="{num(DST_CX)}" y="{num(CLUSTER_CY + 110)}" text-anchor="middle" '
        f'font-size="10.5" letter-spacing="2" fill="{AMBER}">FORGEJO ORG</text>'
    )

    defs = [
        *gradient(
            "linearGradient",
            f'id="trackGrad" gradientUnits="userSpaceOnUse" x1="{num(x_start)}" y1="0" '
            f'x2="{num(x_end)}" y2="0"',
            [("0", CYAN, ""), ("0.5", CYAN_2, ""), ("1", AMBER, "")],
        ),
        *gradient(
            "linearGradient",
            f'id="gateGrad" gradientUnits="userSpaceOnUse" x1="0" y1="{num(GATE_TOP)}" x2="0" '
            f'y2="{num(GATE_BOTTOM)}"',
            [("0", INK_2, "0.55"), ("0.8", INK_3, "0.25"), ("1", INK_3, "0.1")],
        ),
        *gradient(
            "radialGradient",
            'id="gateGlow" cx="0.5" cy="0.5" r="0.5"',
            [("0", CYAN_2, "0.7"), ("1", CYAN_2, "0")],
        ),
        *gradient(
            "radialGradient",
            'id="stateGlow" cx="0.5" cy="0.5" r="0.6"',
            [("0", CYAN_2, "0.22"), ("1", CYAN_2, "0")],
        ),
        *gradient(
            "radialGradient",
            'id="auraSrc" cx="0.5" cy="0.5" r="0.5"',
            [("0", CYAN_3, "0.26"), ("1", CYAN_3, "0")],
        ),
        *gradient(
            "radialGradient",
            'id="auraDst" cx="0.5" cy="0.5" r="0.5"',
            [("0", AMBER, "0.18"), ("1", AMBER, "0")],
        ),
    ]
    scene = "".join(
        [
            f'<ellipse cx="{num(SRC_CX)}" cy="{num(CLUSTER_CY)}" rx="150" ry="140" '
            'fill="url(#auraSrc)" />',
            f'<ellipse cx="{num(DST_CX)}" cy="{num(CLUSTER_CY)}" rx="150" ry="140" '
            'fill="url(#auraDst)" />',
            halo(SRC_CX, CLUSTER_CY, "#CFEFFF"),
            halo(DST_CX, CLUSTER_CY, "#FFE7BF"),
            cluster_links(src_nodes, CYAN, 0.22),
            cluster_links(dst_nodes, AMBER, 0.18),
            "".join(tracks),
            "".join(gates),
            "".join(writes),
            "".join(packets),
            "".join(src),
            "".join(dst),
            state,
            labels,
        ]
    )
    free = [(SRC_CX - 100, 86, DST_CX + 100, 345)]
    return defs, "".join(css), scene, free


# Copy

CARD = {
    "title": "joflux - no lost repos, every stage on record",
    "desc": (
        "A migration run: repositories leave a cluster of GitHub nodes, pass through five stage "
        "gates (export, migrate, monitor, verify, archive) that each write to a state.json "
        "checkpoint, and land in a cluster of Forgejo slots while the originals are archived."
    ),
    "headline": ("No ", "lost", " repos.", "Every stage on record."),
    "body": [
        [("Five stages from a GitHub org to Forgejo or Codeberg,", False)],
        [
            ("each one writing JSON you keep. ", False),
            ("archive", True),
            (" waits for you.", False),
        ],
    ],
    "meta": ["REPEATABLE", "INSPECTABLE", "ZERO DEPS", "CODEBERG"],
    "scene": scene_migration,
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


def main() -> None:
    svg = build_svg()
    svg = svg.replace("__FONT_FACES__", font_faces(svg))
    if "http://" in svg.replace("http://www.w3.org/2000/svg", "") or "https://" in svg:
        raise SystemExit("external reference found in the hero SVG")
    ET.fromstring(svg)  # well-formed, or this raises
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)} ({len(svg.encode()) / 1024:.1f} KiB)")


if __name__ == "__main__":
    main()
