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
from dataclasses import dataclass
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
    cols_used = {c for c, _ in cells}
    if len(cols_used) == 1 and len(rows) >= 3:
        sorted_rs = sorted(rows)
        r_best = sorted_rs[len(sorted_rs) // 2]
    else:
        r_best = max(rows, key=lambda r: (len(rows[r]), -r))
    cs = sorted(rows[r_best])
    others = [(c, r) for c, r in cells if r != r_best]
    row_cx = PAD_X + (cs[0] + cs[-1] + 1) / 2 * cell

    if others:
        icon_cell = max(
            others,
            key=lambda cr: (round(abs(PAD_X + (cr[0] + 0.5) * cell - row_cx), 6), cr[1]),
        )
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


def _keyframes(
    name: str,
    start: float,
    start_offset_rows: int,
    total: float,
    cell: int,
    step: float,
    end_offset_rows: int = 0,
) -> str:
    def pct(s: float) -> str:
        return f"{s / total * 100:.3f}%"

    steps = end_offset_rows - start_offset_rows
    hold = "animation-timing-function:step-end"
    stops = [f"0%{{transform:translateY({start_offset_rows * cell}px);{hold}}}"]
    for k in range(steps + 1):
        stops.append(
            f"{pct(start + k * step)}{{transform:translateY({(start_offset_rows + k) * cell}px);{hold}}}"
        )
    stops.append(f"100%{{transform:translateY({end_offset_rows * cell}px)}}")
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
    skills: list[SkillEntry],
    extra_col: int,
    max_h: int,
    pieces: list[PlacedPiece] | None = None,
    complete_rows: set[int] | None = None,
) -> list[PlacedPiece]:
    """Create AI-tool pieces for the extra column, using an L-tetromino for the top piece when free."""
    used = skills[:max_h]
    n = len(used)
    if n == 0:
        return []
    occupied = {cell for p in (pieces or []) for cell in p.cells}
    cr = complete_rows or set()
    rows_per = max_h // n
    remainder = max_h % n
    result: list[PlacedPiece] = []
    row = 0
    for i, skill in enumerate(used):
        n_rows = rows_per + (1 if i < remainder else 0)
        if (
            i == n - 1
            and n_rows == 2
            and extra_col >= 2
            and row not in cr
            and (row + 1) not in cr
            and (extra_col - 2, row) not in occupied
            and (extra_col - 1, row) not in occupied
        ):
            cells = [
                (extra_col - 2, row),
                (extra_col - 1, row),
                (extra_col, row),
                (extra_col, row + 1),
            ]
        else:
            cells = [(extra_col, row + j) for j in range(n_rows)]
        result.append(PlacedPiece(skill=skill, cells=cells))
        row += n_rows
    return result


@dataclass(frozen=True)
class _ClearStage:
    index: int
    clear_rows: frozenset[int]
    visual_rows: tuple[int, ...]
    flash_start: float
    flash_end: float
    clear_start: float
    clear_end: float
    drop_start: float
    drop_end: float


def _lc_flash_css(name: str, total: float, flash_start: float, flash_end: float) -> str:
    pct = lambda t: f"{t / total * 100:.3f}%"
    dur = flash_end - flash_start
    return (
        f"@keyframes {name}{{"
        f"0%{{opacity:0}}"
        f"{pct(flash_start)}{{opacity:0}}"
        f"{pct(flash_start + 0.25 * dur)}{{opacity:.85}}"
        f"{pct(flash_start + 0.50 * dur)}{{opacity:.15}}"
        f"{pct(flash_start + 0.75 * dur)}{{opacity:.85}}"
        f"{pct(flash_end)}{{opacity:0}}"
        "100%{opacity:0}}"
    )


def _lc_fade_css(name: str, total: float, clear_start: float, clear_end: float) -> str:
    pct = lambda t: f"{t / total * 100:.3f}%"
    return (
        f"@keyframes {name}{{"
        f"0%{{opacity:1}}"
        f"{pct(clear_start)}{{opacity:1}}"
        f"{pct(clear_end)}{{opacity:0}}"
        "100%{opacity:0}}"
    )


def _lc_appear_css(name: str, total: float, clear_start: float, clear_end: float) -> str:
    pct = lambda t: f"{t / total * 100:.3f}%"
    return (
        f"@keyframes {name}{{"
        f"0%{{opacity:0}}"
        f"{pct(clear_start)}{{opacity:0}}"
        f"{pct(clear_end)}{{opacity:1}}"
        "100%{opacity:1}}"
    )


def _lc_drop_segments_css(
    name: str,
    total: float,
    segments: tuple[tuple[float, float, int, int], ...],
) -> str:
    pct = lambda t: f"{t / total * 100:.3f}%"
    stops = ["0%{transform:translateY(0)}"]
    for drop_start, drop_end, from_px, to_px in segments:
        stops.append(
            f"{pct(drop_start)}{{transform:translateY({from_px}px);animation-timing-function:ease-in}}"
        )
        stops.append(f"{pct(drop_end)}{{transform:translateY({to_px}px)}}")
    final_px = segments[-1][3]
    stops.append(f"100%{{transform:translateY({final_px}px)}}")
    return f"@keyframes {name}{{{''.join(stops)}}}"


_LC_AI_PAUSE = 0.45
_LC_STAGE_PAUSE = 0.40
_LC_AI_GAP = 0.15
_LC_PAUSE = 0.20
_LC_FLASH = 0.36
_LC_CLEAR = 0.22
_LC_DROP = 0.36


def _cell_trajectory(
    r: int,
    stages: list[_ClearStage],
    stage_start: int,
    cell: int,
) -> tuple[tuple[tuple[float, float, int, int], ...], int | None]:
    """Return (drop_segments, clear_stage_index) for a cell at row *r*."""
    segments: list[tuple[float, float, int, int]] = []
    cum_drop = 0
    for s in stages:
        if s.index < stage_start:
            continue
        if r in s.clear_rows:
            return tuple(segments), s.index
        n_drop = sum(1 for cr in s.clear_rows if cr < r)
        if n_drop > 0:
            segments.append(
                (s.drop_start, s.drop_end, cum_drop * cell, (cum_drop + n_drop) * cell)
            )
            cum_drop += n_drop
    return tuple(segments), None


def _cut_edges_by_stage(
    g_cells: list[tuple[int, int]],
    full_set: set[tuple[int, int]],
    cell_clear_stage: dict[tuple[int, int], int | None],
    max_h: int,
    cell: int,
    border_color: str,
) -> dict[int, str]:
    """Return {stage_idx: svg_lines} for borders exposed when adjacent cells clear."""
    g_set = set(g_cells)
    by_stage: dict[int, list[str]] = {}
    for c, r in g_cells:
        x, y = _px(c, r, max_h, cell)
        edges = [
            ((c, r + 1), f'<line x1="{x}" y1="{y}" x2="{x + cell}" y2="{y}" stroke="{border_color}" stroke-width="5" stroke-linecap="square"/>'),
            ((c, r - 1), f'<line x1="{x}" y1="{y + cell}" x2="{x + cell}" y2="{y + cell}" stroke="{border_color}" stroke-width="5" stroke-linecap="square"/>'),
            ((c - 1, r), f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y + cell}" stroke="{border_color}" stroke-width="5" stroke-linecap="square"/>'),
            ((c + 1, r), f'<line x1="{x + cell}" y1="{y}" x2="{x + cell}" y2="{y + cell}" stroke="{border_color}" stroke-width="5" stroke-linecap="square"/>'),
        ]
        for nbr, line in edges:
            if nbr not in g_set and nbr in full_set:
                cs = cell_clear_stage.get(nbr)
                if cs is not None:
                    by_stage.setdefault(cs, []).append(line)
    return {k: "".join(v) for k, v in by_stage.items()}


def _piece_svg(
    piece: PlacedPiece,
    anim_name: str,
    total: float,
    max_h: int,
    cell: int,
    border_color: str,
    bg: str,
    stages: list[_ClearStage] | None = None,
    stage_start: int = 0,
    drop_reg: dict[tuple[tuple[float, float, int, int], ...], str] | None = None,
    appear_stages: set[int] | None = None,
    loop: bool = True,
) -> str:
    """Render a single piece group (normal or AI-tool), handling multi-stage line clears."""
    base = piece.skill.color
    icon_name = piece.skill.icon
    dark_text = _luminance(base) > 165
    text_color = bg if dark_text else "#ffffff"
    shadow = "#ffffff" if dark_text else "#000000"
    anim_dur = f"{total:.2f}s"
    iter_mode = "infinite" if loop else "1 both"
    style = f"animation:{anim_name} {anim_dur} linear {iter_mode}"

    text, ix, iy, label_row, icon_cell = _label_and_icon(
        piece.skill.label, piece.cells, text_color, shadow, max_h, cell
    )
    icon_svg = _icon_svg(icon_name, ix, iy, text_color, shadow)

    if not stages:
        parts = [_cell_svg(c, r, base, max_h, cell) for c, r in piece.cells]
        parts.append(_outline_svg(piece.cells, max_h, cell, border_color))
        parts.append(icon_svg)
        parts.append(text)
        return f'<g class="p" style="{style}">{"".join(parts)}</g>'

    cell_traj: dict[tuple[int, int], tuple[tuple[tuple[float, float, int, int], ...], int | None]] = {}
    cell_clear_stage: dict[tuple[int, int], int | None] = {}
    groups: dict[tuple[tuple[tuple[float, float, int, int], ...], int | None], list[tuple[int, int]]] = {}
    for c, r in piece.cells:
        traj = _cell_trajectory(r, stages, stage_start, cell)
        cell_traj[(c, r)] = traj
        cell_clear_stage[(c, r)] = traj[1]
        groups.setdefault(traj, []).append((c, r))

    def _register_drop(segs: tuple[tuple[float, float, int, int], ...]) -> str | None:
        if not segs or drop_reg is None:
            return None
        if segs not in drop_reg:
            drop_reg[segs] = f"lc-drop-{len(drop_reg)}"
        return drop_reg[segs]

    if len(groups) == 1:
        segs, clear_idx = next(iter(groups))
        parts = [_cell_svg(c, r, base, max_h, cell) for c, r in piece.cells]
        parts.append(_outline_svg(piece.cells, max_h, cell, border_color))
        parts.append(icon_svg)
        parts.append(text)
        content = "".join(parts)
        if clear_idx is not None:
            content = f'<g class="lc" style="animation:lc-fade-s{clear_idx} {anim_dur} linear {iter_mode}">{content}</g>'
        drop_name = _register_drop(segs)
        if drop_name is not None:
            content = f'<g class="lc" style="animation:{drop_name} {anim_dur} linear {iter_mode}">{content}</g>'
        return f'<g class="p" style="{style}">{content}</g>'

    full_set = set(piece.cells)
    layers: list[str] = []
    # Keep track of whether the label on label_row has already been placed in a group
    label_placed = False
    for (segs, clear_idx), g_cells in sorted(groups.items(), key=lambda kv: (kv[0][1] is None, kv[0][1] or 0, kv[1])):
        g_rows = {r for _, r in g_cells}
        g_set = set(g_cells)
        g_parts = [_cell_svg(c, r, base, max_h, cell) for c, r in g_cells]
        g_outer, _ = _outline_svg_parts(g_cells, full_set, max_h, cell, border_color)
        g_parts.append(g_outer)

        cut_by_stage = _cut_edges_by_stage(
            g_cells, full_set, cell_clear_stage, max_h, cell, border_color
        )
        for cs, cut_svg in sorted(cut_by_stage.items()):
            if appear_stages is not None:
                appear_stages.add(cs)
            g_parts.append(
                f'<g class="lc" opacity="0" style="animation:lc-appear-s{cs} {anim_dur} linear {iter_mode}">{cut_svg}</g>'
            )

        if icon_cell in g_set:
            g_parts.append(icon_svg)
        if text and not label_placed and label_row in g_rows:
            g_parts.append(text)
            label_placed = True

        g_content = "".join(g_parts)
        if clear_idx is not None:
            g_content = f'<g class="lc" style="animation:lc-fade-s{clear_idx} {anim_dur} linear {iter_mode}">{g_content}</g>'
        drop_name = _register_drop(segs)
        if drop_name is not None:
            g_content = f'<g class="lc" style="animation:{drop_name} {anim_dur} linear {iter_mode}">{g_content}</g>'
        layers.append(g_content)

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
    # ai_plan[i] = (start_t, start_offset_rows, end_offset_rows)
    ai_plan: dict[int, tuple[float, int, int]] = {}
    stages: list[_ClearStage] = []
    drop_reg: dict[tuple[tuple[float, float, int, int], ...], str] = {}
    appear_stages: set[int] = set()

    if lc_active:
        display_cols = cols + 1
        lc_skills = cfg.get_line_clear_skills()
        complete_rows = _find_complete_rows(pieces, cols, max_h)
        ai_pieces = _create_ai_pieces(lc_skills, cols, max_h, pieces, complete_rows)

        cleared_so_far: set[int] = set()
        t = normal_end + _LC_AI_PAUSE
        last_action_end = t

        for i, ap in enumerate(ai_pieces):
            ap_rows = {r for _, r in ap.cells}
            min_r = min(ap_rows)
            prior_drop = sum(1 for cr in cleared_so_far if cr < min_r)
            start_offset = -(max_h + 1 - min_r)
            end_offset = prior_drop
            steps = end_offset - start_offset
            ai_plan[i] = (t, start_offset, end_offset)
            land_t = t + steps * cfg.step
            last_action_end = land_t

            stage_clear = ap_rows & complete_rows
            if stage_clear:
                flash_start = land_t + _LC_PAUSE
                flash_end = flash_start + _LC_FLASH
                clear_start = flash_end
                clear_end = clear_start + _LC_CLEAR
                drop_start = clear_end
                drop_end = drop_start + _LC_DROP
                visual_rows = tuple(
                    r - sum(1 for cr in cleared_so_far if cr < r)
                    for r in sorted(stage_clear)
                )
                stages.append(
                    _ClearStage(
                        index=len(stages),
                        clear_rows=frozenset(stage_clear),
                        visual_rows=visual_rows,
                        flash_start=flash_start,
                        flash_end=flash_end,
                        clear_start=clear_start,
                        clear_end=clear_end,
                        drop_start=drop_start,
                        drop_end=drop_end,
                    )
                )
                cleared_so_far |= stage_clear
                last_action_end = drop_end
                t = drop_end + _LC_STAGE_PAUSE
            else:
                t = land_t + _LC_AI_GAP

        total = last_action_end + cfg.hold
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

    out_pieces: list[str] = []
    # Map each AI piece index to the stage index at which it lands
    ai_stage_start: list[int] = []
    stage_cursor = 0
    for i, ap in enumerate(ai_pieces):
        ai_stage_start.append(stage_cursor)
        ap_rows = {r for _, r in ap.cells}
        if ap_rows & complete_rows:
            stage_cursor += 1

    for i, piece in enumerate(pieces):
        out_pieces.append(
            _piece_svg(
                piece,
                f"f{i}",
                total,
                max_h,
                cell,
                cfg.border_color,
                cfg.background,
                stages or None,
                0,
                drop_reg,
                appear_stages,
                cfg.loop,
            )
        )

    for i, ap in enumerate(ai_pieces):
        out_pieces.append(
            _piece_svg(
                ap,
                f"a{i}",
                total,
                max_h,
                cell,
                cfg.border_color,
                cfg.background,
                stages or None,
                ai_stage_start[i],
                drop_reg,
                appear_stages,
                cfg.loop,
            )
        )

    kf_css = "".join(
        _keyframes(f"f{i}", plan[i][0], -plan[i][1], total, cell, cfg.step)
        for i in range(len(pieces))
    )
    for i, (s_t, s_off, e_off) in ai_plan.items():
        kf_css += _keyframes(f"a{i}", s_t, s_off, total, cell, cfg.step, e_off)

    for s in stages:
        kf_css += _lc_flash_css(f"lc-flash-s{s.index}", total, s.flash_start, s.flash_end)
        kf_css += _lc_fade_css(f"lc-fade-s{s.index}", total, s.clear_start, s.clear_end)
        if s.index in appear_stages:
            kf_css += _lc_appear_css(f"lc-appear-s{s.index}", total, s.clear_start, s.clear_end)

    for segs, name in drop_reg.items():
        kf_css += _lc_drop_segments_css(name, total, segs)

    reduced_classes = ".p"
    if stages:
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
    out.extend(out_pieces)

    anim_dur = f"{total:.2f}s"
    iter_mode = "infinite" if cfg.loop else "1 both"
    for s in stages:
        flash_style = f"animation:lc-flash-s{s.index} {anim_dur} linear {iter_mode}"
        for vr in s.visual_rows:
            x = PAD_X
            y = PAD_TOP + (max_h - 1 - vr) * cell
            out.append(
                f'<rect class="fl" x="{x}" y="{y}" '
                f'width="{display_cols * cell}" height="{cell}" '
                f'fill="#ffffff" opacity="0" style="{flash_style}"/>'
            )

    out.append("</g></svg>")
    return "\n".join(out), total
