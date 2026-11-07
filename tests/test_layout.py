"""Tests for the Stacktris layout engine."""

import pytest

from stacktris.config import SkillEntry, default_config
from stacktris.layout import pack_skills, validate_layout, PlacedPiece


def _skill(name: str, color: str = "#aabbcc", icon: str = "python") -> SkillEntry:
    return SkillEntry(label=name, color=color, icon=icon)


class TestDemoLayout:
    def test_demo_packs_24_pieces(self):
        cfg = default_config()
        pieces, heights = pack_skills(cfg.skills, 14, 11)
        assert len(pieces) == 24

    def test_demo_no_overlaps(self):
        cfg = default_config()
        pieces, heights = pack_skills(cfg.skills, 14, 11)
        all_cells = []
        for p in pieces:
            all_cells.extend(p.cells)
        assert len(all_cells) == len(set(all_cells))

    def test_demo_all_in_bounds(self):
        cfg = default_config()
        pieces, heights = pack_skills(cfg.skills, 14, 11)
        for p in pieces:
            for c, r in p.cells:
                assert 0 <= c < 14
                assert r >= 0

    def test_demo_validation_passes(self):
        cfg = default_config()
        pieces, heights = pack_skills(cfg.skills, 14, 11)
        validate_layout(pieces, 14, heights)

    def test_demo_reproducible(self):
        cfg = default_config()
        p1, h1 = pack_skills(cfg.skills, 14, 11)
        p2, h2 = pack_skills(cfg.skills, 14, 11)
        assert h1 == h2
        for a, b in zip(p1, p2):
            assert a.cells == b.cells


class TestCustomLayout:
    def test_small_set(self):
        skills = [_skill("A"), _skill("B"), _skill("C")]
        pieces, heights = pack_skills(skills, 8, 42)
        assert len(pieces) == 3

    def test_no_overlaps(self):
        skills = [_skill(f"S{i}") for i in range(8)]
        pieces, heights = pack_skills(skills, 10, 99)
        all_cells = []
        for p in pieces:
            all_cells.extend(p.cells)
        assert len(all_cells) == len(set(all_cells))

    def test_all_in_bounds(self):
        skills = [_skill(f"S{i}") for i in range(6)]
        pieces, heights = pack_skills(skills, 8, 7)
        for p in pieces:
            for c, r in p.cells:
                assert 0 <= c < 8
                assert r >= 0


class TestValidation:
    def test_overlap_detected(self):
        p1 = PlacedPiece(skill=_skill("A"), cells=[(0, 0), (1, 0), (2, 0), (3, 0)])
        p2 = PlacedPiece(skill=_skill("B"), cells=[(2, 0), (3, 0), (4, 0), (5, 0)])
        with pytest.raises(ValueError, match="overlapping"):
            validate_layout([p1, p2], 6, [1] * 6)

    def test_out_of_bounds_detected(self):
        p = PlacedPiece(skill=_skill("A"), cells=[(0, 0), (1, 0), (2, 0), (10, 0)])
        with pytest.raises(ValueError, match="out of column bounds"):
            validate_layout([p], 6, [1] * 6)

    def test_negative_row_detected(self):
        p = PlacedPiece(skill=_skill("A"), cells=[(0, -1), (1, 0), (2, 0), (3, 0)])
        with pytest.raises(ValueError, match="negative row"):
            validate_layout([p], 6, [1] * 6)
