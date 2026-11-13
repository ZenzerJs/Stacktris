"""Tests for Stacktris configuration loading and validation."""

import json
import tempfile
from pathlib import Path

import pytest

from stacktris.config import (
    Config,
    SkillEntry,
    default_config,
    default_line_clear_skills,
    load_config,
)


class TestSkillEntry:
    def test_valid_entry(self):
        s = SkillEntry(label="Python", color="#3776ab", icon="python")
        assert s.label == "Python"

    def test_invalid_color(self):
        with pytest.raises(ValueError, match="invalid hex colour"):
            SkillEntry(label="X", color="red", icon="python")

    def test_empty_label(self):
        with pytest.raises(ValueError, match="non-empty"):
            SkillEntry(label="", color="#aabbcc", icon="python")


class TestConfig:
    def test_valid_config(self):
        cfg = Config(
            skills=[SkillEntry(label="Python", color="#3776ab", icon="python")],
        )
        assert len(cfg.skills) == 1

    def test_empty_skills(self):
        with pytest.raises(ValueError, match="at least one"):
            Config(skills=[])

    def test_invalid_background(self):
        with pytest.raises(ValueError, match="invalid hex"):
            Config(
                skills=[SkillEntry(label="X", color="#aabbcc", icon="python")],
                background="notacolor",
            )

    def test_small_cell_size(self):
        with pytest.raises(ValueError, match="cell_size"):
            Config(
                skills=[SkillEntry(label="X", color="#aabbcc", icon="python")],
                cell_size=5,
            )


class TestDefaultConfig:
    def test_returns_24_skills(self):
        cfg = default_config()
        assert len(cfg.skills) == 24

    def test_demo_order(self):
        cfg = default_config()
        assert cfg.skills[0].label == "VERCEL"
        assert cfg.skills[-1].label == "PYTHON"

    def test_html_css_purple(self):
        cfg = default_config()
        html_css = next(s for s in cfg.skills if s.label == "HTML/CSS")
        assert html_css.color == "#8b5cf6"


class TestLoadConfig:
    def test_load_valid(self):
        data = {
            "skills": [{"label": "Python"}, {"label": "Docker"}],
            "board_columns": 8,
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            cfg = load_config(f.name)
        assert len(cfg.skills) == 2
        assert cfg.board_columns == 8
        Path(f.name).unlink()

    def test_load_missing_skills(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"board_columns": 8}, f)
            f.flush()
            with pytest.raises(ValueError, match="skills"):
                load_config(f.name)
        Path(f.name).unlink()

    def test_load_empty_skills(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"skills": []}, f)
            f.flush()
            with pytest.raises(ValueError, match="non-empty"):
                load_config(f.name)
        Path(f.name).unlink()

    def test_load_custom_colors(self):
        data = {
            "skills": [{"label": "Python", "color": "#ff0000"}],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            cfg = load_config(f.name)
        assert cfg.skills[0].color == "#ff0000"
        Path(f.name).unlink()

    def test_unknown_skill_no_color(self):
        data = {"skills": [{"label": "FakeSkill"}]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            with pytest.raises(ValueError, match="not built-in"):
                load_config(f.name)
        Path(f.name).unlink()

    def test_load_line_clear_fields(self):
        data = {
            "skills": [{"label": "Python"}, {"label": "Docker"}],
            "line_clear": False,
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            cfg = load_config(f.name)
        assert cfg.line_clear is False
        Path(f.name).unlink()

    def test_load_line_clear_skills(self):
        data = {
            "skills": [{"label": "Python"}],
            "line_clear_skills": [{"label": "Cursor"}],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            cfg = load_config(f.name)
        assert cfg.line_clear_skills is not None
        assert cfg.line_clear_skills[0].label == "CURSOR"
        Path(f.name).unlink()


class TestLineClearConfig:
    def test_default_line_clear_enabled(self):
        cfg = default_config()
        assert cfg.line_clear is True

    def test_default_line_clear_skills_not_set(self):
        cfg = default_config()
        assert cfg.line_clear_skills is None

    def test_get_line_clear_skills_defaults(self):
        cfg = default_config()
        lc = cfg.get_line_clear_skills()
        assert len(lc) == 3
        labels = {s.label for s in lc}
        assert "CURSOR" in labels
        assert "CLAUDE" in labels
        assert "ANTIGRAVITY" in labels

    def test_get_line_clear_skills_custom(self):
        custom = [SkillEntry(label="MY AI", color="#ff0000", icon="cursor")]
        cfg = Config(
            skills=[SkillEntry(label="Python", color="#3776ab", icon="python")],
            line_clear_skills=custom,
        )
        assert cfg.get_line_clear_skills() == custom

    def test_default_line_clear_skills_helper(self):
        skills = default_line_clear_skills()
        assert len(skills) == 3
        for s in skills:
            assert s.color.startswith("#")
            assert s.icon
