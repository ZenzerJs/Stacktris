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


def _outline_svg_parts(
    subset: list[tuple[int, int]],
    full: set[tuple[int, int]],
    max_h: int,
    cell: int,
    border_color: str,
) -> tuple[str, str]:
    """Return (outer_border_svg, cut_border_svg) for *subset* relative to *full*."""
    sub = set(subset)
    outer: list[str] = []
    cut: list[str] = []
    for c, r in subset:
        x, y = _px(c, r, max_h, cell)
        edges = [
            ((c, r + 1), f'<line x1="{x}" y1="{y}" x2="{x + cell}" y2="{y}" stroke="{border_color}" stroke-width="5" stroke-linecap="square"/>'),
            ((c, r - 1), f'<line x1="{x}" y1="{y + cell}" x2="{x + cell}" y2="{y + cell}" stroke="{border_color}" stroke-width="5" stroke-linecap="square"/>'),
            ((c - 1, r), f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y + cell}" stroke="{border_color}" stroke-width="5" stroke-linecap="square"/>'),
            ((c + 1, r), f'<line x1="{x + cell}" y1="{y}" x2="{x + cell}" y2="{y + cell}" stroke="{border_color}" stroke-width="5" stroke-linecap="square"/>'),
        ]
        for nbr, line in edges:
            if nbr not in sub:
                if nbr in full:
                    cut.append(line)
                else:
                    outer.append(line)
    return "".join(outer), "".join(cut)


def _outline_svg(
    cells: list[tuple[int, int]], max_h: int, cell: int, border_color: str
) -> str:
    outer, _ = _outline_svg_parts(cells, set(cells), max_h, cell, border_color)
    return outer


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
) -> tuple[str, float, float, int, tuple[int, int]]:
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
        return "", ix, iy, r_best, icon_cell

    cx = PAD_X + (label_cells[0] + label_cells[-1] + 1) / 2 * cell
    cy = PAD_TOP + (max_h - 1 - r_best) * cell + cell / 2
    run_px = len(label_cells) * cell - 14

    escaped = xml_escape(label)
    lines = [escaped]
    if " " in label and len(label) * 0.62 * 14 > run_px:
        lines = [xml_escape(w) for w in label.split(" ")]
    elif " " not in label and len(label) * 0.62 * 14 > run_px and len(label) >= 9 and run_px <= 50:
        split_at = 4 if label.upper().startswith("ANTI") and len(label) > 6 else len(label) // 2
        lines = [xml_escape(label[:split_at] + "-"), xml_escape(label[split_at:])]
    fs = min(14, run_px / (max(len(l) for l in lines) * 0.66))
    style = f"fill:{text_color};stroke:{shadow};stroke-opacity:.45"

    if len(lines) == 1:
        text = f'<text x="{cx:.1f}" y="{cy:.1f}" font-size="{fs:.1f}" style="{style}">{lines[0]}</text>'
    else:
        text = (
            f'<text x="{cx:.1f}" y="{cy - fs * .6:.1f}" font-size="{fs:.1f}" style="{style}">{lines[0]}</text>'
            f'<text x="{cx:.1f}" y="{cy + fs * .6:.1f}" font-size="{fs:.1f}" style="{style}">{lines[1]}</text>'
        )

    return text, ix, iy, r_best, icon_cell


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
    dur = flash_end - flash_start
    return (
        "@keyframes lc-flash{"
        f"0%{{opacity:0}}"
        f"{pct(flash_start)}{{opacity:0}}"
        f"{pct(flash_start + 0.25 * dur)}{{opacity:.85}}"
        f"{pct(flash_start + 0.50 * dur)}{{opacity:.15}}"
        f"{pct(flash_start + 0.75 * dur)}{{opacity:.85}}"
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


def _lc_appear_css(total: float, clear_start: float, clear_end: float) -> str:
    pct = lambda t: f"{t / total * 100:.3f}%"
    return (
        "@keyframes lc-appear{"
        f"0%{{opacity:0}}"
        f"{pct(clear_start)}{{opacity:0}}"
        f"{pct(clear_end)}{{opacity:1}}"
        "100%{opacity:1}}"
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
_LC_AI_GAP = 0.08
_LC_PAUSE = 0.20
_LC_FLASH = 0.36
_LC_CLEAR = 0.20
_LC_DROP = 0.36


def _piece_svg(
    piece: PlacedPiece,
    anim_name: str,
    total: float,
    max_h: int,
    cell: int,
    border_color: str,
    bg: str,
    complete_rows: set[int] | None = None,
) -> str:
    """Render a single piece group (normal or AI-tool), handling partial line clears."""
    base = piece.skill.color
    icon_name = piece.skill.icon
    dark_text = _luminance(base) > 165
    text_color = bg if dark_text else "#ffffff"
    shadow = "#ffffff" if dark_text else "#000000"
    anim_dur = f"{total:.2f}s"
    style = f"animation:{anim_name} {anim_dur} linear 1 both"

    text, ix, iy, label_row, icon_cell = _label_and_icon(
        piece.skill.label, piece.cells, text_color, shadow, max_h, cell
    )
    icon_svg = _icon_svg(icon_name, ix, iy, text_color, shadow)

    if not complete_rows:
        parts = [_cell_svg(c, r, base, max_h, cell) for c, r in piece.cells]
        parts.append(_outline_svg(piece.cells, max_h, cell, border_color))
        parts.append(icon_svg)
        parts.append(text)
        return f'<g class="p" style="{style}">{"".join(parts)}</g>'

    cleared = [(c, r) for c, r in piece.cells if r in complete_rows]
    surviving = [(c, r) for c, r in piece.cells if r not in complete_rows]
    groups: dict[int, list[tuple[int, int]]] = {}
    for c, r in surviving:
        n_drop = sum(1 for cr in complete_rows if cr < r)
        groups.setdefault(n_drop, []).append((c, r))

    if not surviving:
        parts = [_cell_svg(c, r, base, max_h, cell) for c, r in piece.cells]
        parts.append(_outline_svg(piece.cells, max_h, cell, border_color))
        parts.append(icon_svg)
        parts.append(text)
        inner = f"animation:lc-fade {anim_dur} linear 1 both"
        return f'<g class="p" style="{style}"><g class="lc" style="{inner}">{"".join(parts)}</g></g>'

    if not cleared and len(groups) == 1:
        n_drop = next(iter(groups))
        parts = [_cell_svg(c, r, base, max_h, cell) for c, r in piece.cells]
        parts.append(_outline_svg(piece.cells, max_h, cell, border_color))
        parts.append(icon_svg)
        parts.append(text)
        content = "".join(parts)
        if n_drop > 0:
            inner = f"animation:lc-drop-{n_drop} {anim_dur} linear 1 both"
            content = f'<g class="lc" style="{inner}">{content}</g>'
        return f'<g class="p" style="{style}">{content}</g>'

    # Mixed piece: cells in cleared rows fade out; surviving cells keep borders and drop.
    full_set = set(piece.cells)
    layers: list[str] = []

    if cleared:
        c_parts = [_cell_svg(c, r, base, max_h, cell) for c, r in cleared]
        c_outer, _ = _outline_svg_parts(cleared, full_set, max_h, cell, border_color)
        c_parts.append(c_outer)
        if icon_cell[1] in complete_rows:
            c_parts.append(icon_svg)
        if text and label_row in complete_rows:
            c_parts.append(text)
        c_style = f"animation:lc-fade {anim_dur} linear 1 both"
        layers.append(f'<g class="lc" style="{c_style}">{"".join(c_parts)}</g>')

    for n_drop, g_cells in sorted(groups.items()):
        g_rows = {r for _, r in g_cells}
        g_set = set(g_cells)
        s_parts = [_cell_svg(c, r, base, max_h, cell) for c, r in g_cells]
        s_outer, s_cut = _outline_svg_parts(g_cells, full_set, max_h, cell, border_color)
        s_parts.append(s_outer)
        if s_cut:
            appear_style = f"animation:lc-appear {anim_dur} linear 1 both"
            s_parts.append(f'<g class="lc" opacity="0" style="{appear_style}">{s_cut}</g>')
        if icon_cell in g_set:
            s_parts.append(icon_svg)
        if text and label_row in g_rows:
            s_parts.append(text)
        s_content = "".join(s_parts)
        if n_drop > 0:
            s_style = f"animation:lc-drop-{n_drop} {anim_dur} linear 1 both"
            s_content = f'<g class="lc" style="{s_style}">{s_content}</g>'
        layers.append(s_content)

    return f'<g class="p" style="{style}">{"".join(layers)}</g>'


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
    drop_keyframes: dict[int, str] = {}
    has_cut_edges = False

    if lc_active:
        display_cols = cols + 1
        lc_skills = cfg.get_line_clear_skills()
        complete_rows = _find_complete_rows(pieces, cols, max_h)
        ai_pieces = _create_ai_pieces(lc_skills, cols, max_h)

        ai_start = normal_end + _LC_AI_PAUSE
        t = ai_start
        for i, ap in enumerate(ai_pieces):
            rows_fall = max_h + 1 - min(r for _, r in ap.cells)
            ai_plan[i] = (t, rows_fall)
            t = t + rows_fall * cfg.step + _LC_AI_GAP
        ai_end = max(
            (ai_plan[i][0] + ai_plan[i][1] * cfg.step for i in ai_plan),
            default=ai_start,
        )

        if complete_rows:
            flash_start = ai_end + _LC_PAUSE
            flash_end = flash_start + _LC_FLASH
            clear_start = flash_end
            clear_end = clear_start + _LC_CLEAR
            drop_start = clear_end
            drop_end = drop_start + _LC_DROP
            total = drop_end + cfg.hold

            for p in [*pieces, *ai_pieces]:
                p_rows = {r for _, r in p.cells}
                if (p_rows & complete_rows) and (p_rows - complete_rows):
                    has_cut_edges = True
                for _, r in p.cells:
                    if r not in complete_rows:
                        n_drop = sum(1 for cr in complete_rows if cr < r)
                        if n_drop > 0 and n_drop not in drop_keyframes:
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
        if has_cut_edges:
            kf_css += _lc_appear_css(total, clear_start, clear_end)
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

    row_filter = complete_rows if (lc_active and complete_rows) else None
    for i, piece in enumerate(pieces):
        out.append(_piece_svg(
            piece, f"f{i}", total, max_h, cell, cfg.border_color, cfg.background, row_filter
        ))

    for i, ap in enumerate(ai_pieces):
        out.append(_piece_svg(
            ap, f"a{i}", total, max_h, cell, cfg.border_color, cfg.background, row_filter
        ))

    if lc_active and complete_rows:
        anim_dur = f"{total:.2f}s"
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
