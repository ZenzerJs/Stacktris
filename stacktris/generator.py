"""SVG generator for Stacktris falling-block tech-stack graphics.

Produces a self-contained animated SVG with:
- Tetris-style bevelled tile board
- Brand logos from Simple Icons (embedded, no external resources)
- CSS keyframe falling animation with wave staggering
- prefers-reduced-motion support
- Accessible title/description
"""

from __future__ import annotations

import random
from xml.sax.saxutils import escape as xml_escape

from .config import Config, SkillEntry
from .icons import ICONS
from .layout import PlacedPiece, validate_layout


PAD_X = 40
PAD_TOP = 96
PAD_BOT = 36


def _shade(hexc: str, f: float) -> str:
    h = hexc.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    if f >= 0:
        r, g, b = (int(v + (255 - v) * f) for v in (r, g, b))
    else:
        r, g, b = (int(v * (1 + f)) for v in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def _luminance(hexc: str) -> float:
    h = hexc.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _px(c: int, r: int, max_h: int, cell: int) -> tuple[int, int]:
    return PAD_X + c * cell, PAD_TOP + (max_h - 1 - r) * cell


def _cell_svg(c: int, r: int, base: str, max_h: int, cell: int) -> str:
    x, y = _px(c, r, max_h, cell)
    b, s = 7, cell
    return (
        f'<rect x="{x}" y="{y}" width="{s}" height="{s}" fill="{base}"/>'
        f'<polygon points="{x},{y} {x+s},{y} {x+s-b},{y+b} {x+b},{y+b}" fill="{_shade(base, .35)}"/>'
        f'<polygon points="{x},{y} {x+b},{y+b} {x+b},{y+s-b} {x},{y+s}" fill="{_shade(base, .15)}"/>'
        f'<polygon points="{x+s},{y} {x+s},{y+s} {x+s-b},{y+s-b} {x+s-b},{y+b}" fill="{_shade(base, -.15)}"/>'
        f'<polygon points="{x},{y+s} {x+s},{y+s} {x+s-b},{y+s-b} {x+b},{y+s-b}" fill="{_shade(base, -.35)}"/>'
    )


def _outline_svg(
    cells: list[tuple[int, int]], max_h: int, cell: int, border_color: str
) -> str:
    cs = set(cells)
    out: list[str] = []
    for c, r in cells:
        x, y = _px(c, r, max_h, cell)
        if (c, r + 1) not in cs:
            out.append(
                f'<line x1="{x}" y1="{y}" x2="{x + cell}" y2="{y}" '
                f'stroke="{border_color}" stroke-width="5" stroke-linecap="square"/>'
            )
        if (c, r - 1) not in cs:
            out.append(
                f'<line x1="{x}" y1="{y + cell}" x2="{x + cell}" y2="{y + cell}" '
                f'stroke="{border_color}" stroke-width="5" stroke-linecap="square"/>'
            )
        if (c - 1, r) not in cs:
            out.append(
                f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y + cell}" '
                f'stroke="{border_color}" stroke-width="5" stroke-linecap="square"/>'
            )
        if (c + 1, r) not in cs:
            out.append(
                f'<line x1="{x + cell}" y1="{y}" x2="{x + cell}" y2="{y + cell}" '
                f'stroke="{border_color}" stroke-width="5" stroke-linecap="square"/>'
            )
    return "".join(out)


def _glyph(slug: str, x: float, y: float, size: float, color: str, shadow: str) -> str:
    t = f"translate({x:.1f},{y:.1f}) scale({size / 24:.4f})"
    d = ICONS[slug]
    return (
        f'<path transform="{t}" d="{d}" fill="{shadow}" fill-opacity=".4" '
        f'stroke="{shadow}" stroke-opacity=".4" stroke-width="{2.2 * 24 / size:.2f}" '
        f'stroke-linejoin="round"/>'
        f'<path transform="{t}" d="{d}" fill="{color}"/>'
    )


def _icon_svg(name: str, cx: float, cy: float, color: str, shadow: str) -> str:
    parts = name.split("+")
    if len(parts) == 1:
        return _glyph(name, cx - 15, cy - 15, 30, color, shadow)
    s = 20
    return "".join(
        _glyph(p, cx - s - 1 + k * (s + 2), cy - s / 2, s, color, shadow)
        for k, p in enumerate(parts)
    )


def _label_and_icon(
    label: str,
    cells: list[tuple[int, int]],
    text_color: str,
    shadow: str,
    max_h: int,
    cell: int,
) -> tuple[str, float, float]:
    rows: dict[int, list[int]] = {}
    for c, r in cells:
        rows.setdefault(r, []).append(c)
    r_best = max(rows, key=lambda r: (len(rows[r]), -r))
    cs = sorted(rows[r_best])
    others = [(c, r) for c, r in cells if r != r_best]
    row_cx = PAD_X + (cs[0] + cs[-1] + 1) / 2 * cell

    if others:
        icon_cell = max(others, key=lambda cr: abs(PAD_X + (cr[0] + 0.5) * cell - row_cx))
        label_cells = cs
    else:
        icon_cell = (cs[0], r_best)
        label_cells = cs[1:]

    ix = PAD_X + (icon_cell[0] + 0.5) * cell
    iy = PAD_TOP + (max_h - 1 - icon_cell[1]) * cell + cell / 2

    if not label_cells:
        return "", ix, iy

    cx = PAD_X + (label_cells[0] + label_cells[-1] + 1) / 2 * cell
    cy = PAD_TOP + (max_h - 1 - r_best) * cell + cell / 2
    run_px = len(label_cells) * cell - 14

    escaped = xml_escape(label)
    lines = [escaped]
    if " " in label and len(label) * 0.62 * 14 > run_px:
        lines = [xml_escape(w) for w in label.split(" ")]
    fs = min(14, run_px / (max(len(l) for l in lines) * 0.66))
    style = f"fill:{text_color};stroke:{shadow};stroke-opacity:.45"

    if len(lines) == 1:
        text = f'<text x="{cx:.1f}" y="{cy:.1f}" font-size="{fs:.1f}" style="{style}">{lines[0]}</text>'
    else:
        text = (
            f'<text x="{cx:.1f}" y="{cy - fs * .6:.1f}" font-size="{fs:.1f}" style="{style}">{lines[0]}</text>'
            f'<text x="{cx:.1f}" y="{cy + fs * .6:.1f}" font-size="{fs:.1f}" style="{style}">{lines[1]}</text>'
        )

    return text, ix, iy


def _plan_waves(
    pieces: list[PlacedPiece],
    heights: list[int],
    cfg: Config,
) -> tuple[dict[int, tuple[float, int]], float]:
    """Group pieces into staggered waves for the falling animation."""
    n = len(pieces)
    max_h = max(heights)

    where: dict[tuple[int, int], int] = {}
    for i, p in enumerate(pieces):
        for cell in p.cells:
            where[cell] = i

    below: list[set[int]] = [set() for _ in range(n)]
    for i, p in enumerate(pieces):
        for c, r in p.cells:
            for rr in range(r):
                j = where.get((c, rr))
                if j is not None and j != i:
                    below[i].add(j)

    def low(i: int) -> tuple[int, int]:
        return (min(r for _, r in pieces[i].cells), min(c for c, _ in pieces[i].cells))

    rng = random.Random(cfg.seed)
    placed: set[int] = set()
    remaining = set(range(n))
    plan: dict[int, tuple[float, int]] = {}
    t = cfg.start_delay

    while remaining:
        ready = sorted((i for i in remaining if below[i] <= placed), key=low)
        if not ready:
            raise ValueError("layout has interlocking pieces that cannot be dropped in order")
        pool = ready[:6]
        chosen = rng.sample(pool, min(rng.choice([2, 3]), len(pool)))
        wave_end = t
        for k, i in enumerate(sorted(chosen, key=low)):
            rows = max_h + 1 - min(r for _, r in pieces[i].cells)
            start = t + k * cfg.stagger
            plan[i] = (start, rows)
            wave_end = max(wave_end, start + rows * cfg.step)
        placed |= set(chosen)
        remaining -= set(chosen)
        t = wave_end + cfg.wave_pause

    return plan, t


def _keyframes(name: str, start: float, rows: int, total: float, cell: int, step: float) -> str:
    def pct(s: float) -> str:
        return f"{s / total * 100:.3f}%"

    hold = "animation-timing-function:step-end"
    stops = [f"0%{{transform:translateY({-rows * cell}px);{hold}}}"]
    for k in range(rows + 1):
        stops.append(
            f"{pct(start + k * step)}{{transform:translateY({-(rows - k) * cell}px);{hold}}}"
        )
    stops.append("100%{transform:translateY(0)}")
    return f"@keyframes {name}{{{''.join(stops)}}}"


def _find_complete_rows(
    pieces: list[PlacedPiece], cols: int, max_h: int
) -> set[int]:
    """Return the set of row indices that are fully filled across all *cols* columns."""
    occupied: set[tuple[int, int]] = set()
    for p in pieces:
        for cell in p.cells:
            occupied.add(cell)
    return {r for r in range(max_h) if all((c, r) in occupied for c in range(cols))}


def _create_ai_pieces(
    skills: list[SkillEntry], extra_col: int, max_h: int
) -> list[PlacedPiece]:
    """Create vertical AI-tool pieces that fill the extra column from row 0 to max_h-1."""
    used = skills[:max_h]
    n = len(used)
    if n == 0:
        return []
    rows_per = max_h // n
    remainder = max_h % n
    result: list[PlacedPiece] = []
    row = 0
    for i, skill in enumerate(used):
        n_rows = rows_per + (1 if i < remainder else 0)
        cells = [(extra_col, row + j) for j in range(n_rows)]
        result.append(PlacedPiece(skill=skill, cells=cells))
        row += n_rows
    return result


def _lc_flash_css(total: float, flash_start: float, flash_end: float) -> str:
    pct = lambda t: f"{t / total * 100:.3f}%"
    mid = (flash_start + flash_end) / 2
    return (
        "@keyframes lc-flash{"
        f"0%{{opacity:0}}"
        f"{pct(flash_start)}{{opacity:0}}"
        f"{pct(mid)}{{opacity:.7}}"
        f"{pct(flash_end)}{{opacity:0}}"
        "100%{opacity:0}}"
    )


def _lc_fade_css(total: float, clear_start: float, clear_end: float) -> str:
    pct = lambda t: f"{t / total * 100:.3f}%"
    return (
        "@keyframes lc-fade{"
        f"0%{{opacity:1}}"
        f"{pct(clear_start)}{{opacity:1}}"
        f"{pct(clear_end)}{{opacity:0}}"
        "100%{opacity:0}}"
    )


def _lc_drop_css(
    name: str, total: float, drop_start: float, drop_end: float, drop_px: int
) -> str:
    pct = lambda t: f"{t / total * 100:.3f}%"
    return (
        f"@keyframes {name}{{"
        f"0%{{transform:translateY(0)}}"
        f"{pct(drop_start)}{{transform:translateY(0);animation-timing-function:ease-in}}"
        f"{pct(drop_end)}{{transform:translateY({drop_px}px)}}"
        f"100%{{transform:translateY({drop_px}px)}}"
        "}}"
    )


_LC_AI_PAUSE = 0.25
_LC_AI_STAGGER = 0.15
_LC_PAUSE = 0.2
_LC_FLASH = 0.3
_LC_SETTLE = 0.4


def _piece_svg(
    piece: PlacedPiece,
    anim_name: str,
    total: float,
    max_h: int,
    cell: int,
    border_color: str,
    bg: str,
    inner_style: str | None = None,
) -> str:
    """Render a single piece group (normal or AI-tool)."""
    base = piece.skill.color
    icon_name = piece.skill.icon
    dark_text = _luminance(base) > 165
    text_color = bg if dark_text else "#ffffff"
    shadow = "#ffffff" if dark_text else "#000000"
    style = f"animation:{anim_name} {total:.2f}s linear 1 both"

    parts: list[str] = []
    for c, r in piece.cells:
        parts.append(_cell_svg(c, r, base, max_h, cell))
    parts.append(_outline_svg(piece.cells, max_h, cell, border_color))
    text, ix, iy = _label_and_icon(
        piece.skill.label, piece.cells, text_color, shadow, max_h, cell
    )
    parts.append(_icon_svg(icon_name, ix, iy, text_color, shadow))
    parts.append(text)
    content = "".join(parts)

    if inner_style:
        content = f'<g class="lc" style="{inner_style}">{content}</g>'
    return f'<g class="p" style="{style}">{content}</g>'


def generate(
    pieces: list[PlacedPiece],
    heights: list[int],
    cfg: Config,
) -> tuple[str, float]:
    """Generate the full SVG string. Returns (svg_text, animation_duration_seconds)."""
    cols = cfg.board_columns
    cell = cfg.cell_size
    max_h = max(heights) if heights else 1

    validate_layout(pieces, cols, heights)
    plan, normal_end = _plan_waves(pieces, heights, cfg)

    lc_active = cfg.line_clear and max_h > 0
    complete_rows: set[int] = set()
    ai_pieces: list[PlacedPiece] = []
    ai_plan: dict[int, tuple[float, int]] = {}
    piece_lc: dict[int, str | None] = {}
    ai_lc: dict[int, str | None] = {}
    drop_keyframes: dict[int, str] = {}

    if lc_active:
        display_cols = cols + 1
        lc_skills = cfg.get_line_clear_skills()
        complete_rows = _find_complete_rows(pieces, cols, max_h)
        ai_pieces = _create_ai_pieces(lc_skills, cols, max_h)

        ai_start = normal_end + _LC_AI_PAUSE
        for i, ap in enumerate(ai_pieces):
            start_t = ai_start + i * _LC_AI_STAGGER
            rows_fall = max_h + 1 - min(r for _, r in ap.cells)
            ai_plan[i] = (start_t, rows_fall)
        ai_end = max(
            ai_plan[i][0] + ai_plan[i][1] * cfg.step for i in ai_plan
        ) if ai_plan else ai_start

        if complete_rows:
            flash_start = ai_end + _LC_PAUSE
            flash_end = flash_start + _LC_FLASH
            clear_start = flash_end
            clear_end = clear_start + _LC_SETTLE * 0.5
            drop_start = flash_end
            drop_end = drop_start + _LC_SETTLE
            total = drop_end + cfg.hold

            for i, p in enumerate(pieces):
                cell_rows = {r for _, r in p.cells}
                if cell_rows & complete_rows:
                    piece_lc[i] = "fade"
                else:
                    min_r = min(r for _, r in p.cells)
                    n_drop = sum(1 for r in complete_rows if r < min_r)
                    if n_drop > 0:
                        piece_lc[i] = f"drop-{n_drop}"
                        drop_keyframes[n_drop] = _lc_drop_css(
                            f"lc-drop-{n_drop}", total, drop_start, drop_end, n_drop * cell
                        )

            for i, ap in enumerate(ai_pieces):
                cell_rows = {r for _, r in ap.cells}
                if cell_rows & complete_rows:
                    ai_lc[i] = "fade"
                else:
                    min_r = min(r for _, r in ap.cells)
                    n_drop = sum(1 for r in complete_rows if r < min_r)
                    if n_drop > 0:
                        ai_lc[i] = f"drop-{n_drop}"
                        drop_keyframes[n_drop] = _lc_drop_css(
                            f"lc-drop-{n_drop}", total, drop_start, drop_end, n_drop * cell
                        )
        else:
            total = ai_end + cfg.hold
    else:
        display_cols = cols
        total = normal_end + cfg.hold

    w = PAD_X * 2 + display_cols * cell
    h = PAD_TOP + max_h * cell + PAD_BOT

    title_escaped = xml_escape(cfg.title)
    all_labels = [p.skill.label for p in pieces]
    if ai_pieces:
        all_labels += [ap.skill.label for ap in ai_pieces]
    desc = f"Falling-block graphic showing tech skills: {', '.join(all_labels)}"
    desc_escaped = xml_escape(desc)

    kf_css = "".join(
        _keyframes(f"f{i}", plan[i][0], plan[i][1], total, cell, cfg.step)
        for i in range(len(pieces))
    )
    for i in ai_plan:
        kf_css += _keyframes(f"a{i}", ai_plan[i][0], ai_plan[i][1], total, cell, cfg.step)

    if lc_active and complete_rows:
        kf_css += _lc_flash_css(total, flash_start, flash_end)
        kf_css += _lc_fade_css(total, clear_start, clear_end)
        kf_css += "".join(drop_keyframes.values())

    reduced_classes = ".p"
    if lc_active and complete_rows:
        reduced_classes = ".p,.lc,.fl"

    out: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" '
        f'aria-label="{xml_escape(desc)}">',
        f"<title>{title_escaped}</title>",
        f"<desc>{desc_escaped}</desc>",
        "<style>"
        'text{font-family:"Segoe UI",Verdana,Helvetica,Arial,sans-serif;font-weight:800;'
        "stroke-width:3px;paint-order:stroke;text-anchor:middle;dominant-baseline:central;"
        "letter-spacing:.4px}"
        ".t{font-size:30px;text-anchor:start;fill:#fff;stroke:none;letter-spacing:1px}"
        f"@media (prefers-reduced-motion:reduce){{{reduced_classes}{{animation:none!important}}}}"
        + kf_css
        + "</style>",
        f'<defs><clipPath id="well"><rect x="0" y="{PAD_TOP - 4}" '
        f'width="{w}" height="{h - PAD_TOP + 4}"/></clipPath></defs>',
        f'<rect width="{w}" height="{h}" rx="18" fill="{cfg.background}"/>',
        f'<text class="t" x="{PAD_X}" y="52">{title_escaped}</text>',
        f'<line x1="{PAD_X}" y1="74" x2="{w - PAD_X}" y2="74" '
        f'stroke="{cfg.separator_color}" stroke-width="2"/>',
    ]

    for c in range(display_cols):
        for r in range(max_h):
            x, y = _px(c, r, max_h, cell)
            out.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'fill="none" stroke="{cfg.grid_color}"/>'
            )

    out.append('<g clip-path="url(#well)">')

    anim_dur = f"{total:.2f}s"
    for i, piece in enumerate(pieces):
        inner = None
        lc_type = piece_lc.get(i)
        if lc_type == "fade":
            inner = f"animation:lc-fade {anim_dur} linear 1 both"
        elif lc_type is not None:
            inner = f"animation:lc-{lc_type} {anim_dur} linear 1 both"
        out.append(_piece_svg(
            piece, f"f{i}", total, max_h, cell, cfg.border_color, cfg.background, inner
        ))

    for i, ap in enumerate(ai_pieces):
        inner = None
        lc_type = ai_lc.get(i)
        if lc_type == "fade":
            inner = f"animation:lc-fade {anim_dur} linear 1 both"
        elif lc_type is not None:
            inner = f"animation:lc-{lc_type} {anim_dur} linear 1 both"
        out.append(_piece_svg(
            ap, f"a{i}", total, max_h, cell, cfg.border_color, cfg.background, inner
        ))

    if lc_active and complete_rows:
        flash_style = f"animation:lc-flash {anim_dur} linear 1 both"
        for r in sorted(complete_rows):
            x = PAD_X
            y = PAD_TOP + (max_h - 1 - r) * cell
            out.append(
                f'<rect class="fl" x="{x}" y="{y}" '
                f'width="{display_cols * cell}" height="{cell}" '
                f'fill="#ffffff" opacity="0" style="{flash_style}"/>'
            )

    out.append("</g></svg>")
    return "\n".join(out), total
