"""Tetromino packing layout engine for Stacktris.

Each skill is mapped to a standard tetromino shape (I/O/T/S/Z/L/J) and placed
on the board with validated no-overlap, no-out-of-bounds guarantees.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from .config import Config, SkillEntry

TETROMINOES = [
    [(0, 0), (1, 0), (2, 0), (3, 0)],       # I horizontal
    [(0, 0), (0, 1), (0, 2), (0, 3)],       # I vertical
    [(0, 0), (1, 0), (0, 1), (1, 1)],       # O
    [(0, 0), (1, 0), (2, 0), (1, 1)],       # T up
    [(0, 0), (0, 1), (0, 2), (1, 1)],       # T right
    [(0, 0), (1, 0), (2, 0), (0, 1)],       # L
    [(0, 0), (1, 0), (1, 1), (1, 2)],       # L rotated
    [(0, 0), (1, 0), (0, 1), (0, 2)],       # J
    [(0, 0), (1, 0), (2, 0), (2, 1)],       # J rotated
    [(0, 0), (1, 0), (1, 1), (2, 1)],       # S
    [(0, 0), (0, 1), (1, 1), (1, 2)],       # S vertical
    [(1, 0), (2, 0), (0, 1), (1, 1)],       # Z
    [(0, 0), (0, 1), (1, 1), (1, 2)],       # Z vertical (same shape as S vert for offsets)
]

_DEMO_LAYOUT: list[tuple[str, list[tuple[int, int]]]] = [
    ("VERCEL", [(0, 0), (0, 1), (0, 2), (1, 2)]),
    ("DOCKER", [(1, 0), (1, 1), (2, 1), (3, 1)]),
    ("GITHUB ACTIONS", [(2, 0), (3, 0), (4, 0), (5, 0)]),
    ("PRISMA", [(4, 1), (5, 1), (6, 0), (6, 1)]),
    ("SQLITE", [(7, 0), (8, 0), (8, 1), (8, 2)]),
    ("VITEST", [(9, 0), (9, 1), (10, 1), (10, 2)]),
    ("PLAYWRIGHT", [(10, 0), (11, 0), (11, 1), (11, 2)]),
    ("TYPST", [(12, 0), (12, 1), (13, 0), (13, 1)]),
    ("LANGCHAIN", [(6, 2), (6, 3), (7, 1), (7, 2)]),
    ("LANGGRAPH", [(2, 2), (2, 3), (2, 4), (3, 2)]),
    ("OLLAMA", [(3, 3), (4, 2), (4, 3), (5, 2)]),
    ("FASTAPI", [(9, 2), (9, 3), (10, 3), (11, 3)]),
    ("PYTORCH", [(12, 2), (12, 3), (12, 4), (13, 2)]),
    ("MEDIAPIPE", [(0, 3), (0, 4), (1, 3), (1, 4)]),
    ("NODE.JS", [(5, 3), (5, 4), (6, 4), (6, 5)]),
    ("TAILWIND", [(7, 3), (7, 4), (7, 5), (8, 5)]),
    ("REACT", [(8, 3), (8, 4), (9, 4), (9, 5)]),
    ("NEXT.JS", [(12, 5), (13, 3), (13, 4), (13, 5)]),
    ("HTML/CSS", [(3, 4), (4, 4), (4, 5), (5, 5)]),
    ("JAVA", [(10, 4), (11, 4), (11, 5), (11, 6)]),
    ("SWIFT", [(0, 5), (0, 6), (1, 5), (2, 5)]),
    ("JAVASCRIPT", [(2, 6), (2, 7), (3, 5), (3, 6)]),
    ("TYPESCRIPT", [(9, 6), (10, 5), (10, 6), (10, 7)]),
    ("PYTHON", [(5, 6), (6, 6), (6, 7), (7, 6)]),
]


@dataclass
class PlacedPiece:
    """A skill with its cells assigned on the board."""

    skill: SkillEntry
    cells: list[tuple[int, int]]


def _is_demo_set(skills: list[SkillEntry]) -> bool:
    """Check whether the skill set matches the demo layout exactly."""
    demo_labels = [name for name, _ in _DEMO_LAYOUT]
    return [s.label for s in skills] == demo_labels


def _try_place(
    shape: list[tuple[int, int]],
    col: int,
    row: int,
    occupied: set[tuple[int, int]],
    cols: int,
) -> list[tuple[int, int]] | None:
    """Try to place shape at (col, row); returns cells or None if blocked."""
    cells = [(c + col, r + row) for c, r in shape]
    for c, r in cells:
        if c < 0 or c >= cols or r < 0:
            return None
        if (c, r) in occupied:
            return None
    return cells


def pack_skills(
    skills: list[SkillEntry],
    cols: int,
    seed: int,
) -> tuple[list[PlacedPiece], list[int]]:
    """Pack skills as tetrominoes on a board.

    Returns placed pieces and the column heights (cells filled per column).
    Raises ValueError if packing fails (e.g. too many skills for the board width).
    """
    if _is_demo_set(skills):
        pieces = []
        for skill, (label, cells) in zip(skills, _DEMO_LAYOUT):
            pieces.append(PlacedPiece(skill=skill, cells=cells))
        heights = [0] * cols
        for p in pieces:
            for c, r in p.cells:
                heights[c] = max(heights[c], r + 1)
        return pieces, heights

    rng = random.Random(seed)
    occupied: set[tuple[int, int]] = set()
    pieces: list[PlacedPiece] = []
    shapes_pool = list(TETROMINOES)

    for skill in skills:
        placed = False
        rng.shuffle(shapes_pool)
        for shape in shapes_pool:
            for row in range(100):
                for col in range(cols):
                    cells = _try_place(shape, col, row, occupied, cols)
                    if cells is not None:
                        occupied.update(cells)
                        pieces.append(PlacedPiece(skill=skill, cells=cells))
                        placed = True
                        break
                if placed:
                    break
            if placed:
                break
        if not placed:
            raise ValueError(
                f"could not place skill {skill.label!r} on a {cols}-column board — "
                f"try increasing board_columns or reducing the number of skills"
            )

    heights = [0] * cols
    for c, r in occupied:
        if c < cols:
            heights[c] = max(heights[c], r + 1)

    return pieces, heights


def validate_layout(
    pieces: list[PlacedPiece],
    cols: int,
    heights: Sequence[int],
) -> None:
    """Validate no overlaps and all cells are in bounds."""
    all_cells: list[tuple[int, int]] = []
    for p in pieces:
        for c, r in p.cells:
            if c < 0 or c >= cols:
                raise ValueError(
                    f"piece {p.skill.label!r} cell ({c},{r}) out of column bounds [0,{cols})"
                )
            if r < 0:
                raise ValueError(
                    f"piece {p.skill.label!r} cell ({c},{r}) has negative row"
                )
            all_cells.append((c, r))
    if len(all_cells) != len(set(all_cells)):
        seen: set[tuple[int, int]] = set()
        for cell in all_cells:
            if cell in seen:
                raise ValueError(f"overlapping cell {cell}")
            seen.add(cell)
