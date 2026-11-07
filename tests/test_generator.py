"""Tests for the Stacktris SVG generator."""

import xml.etree.ElementTree as ET

import pytest

from stacktris.config import Config, SkillEntry, default_config
from stacktris.generator import generate
from stacktris.layout import pack_skills


def _make_svg(cfg: Config | None = None) -> tuple[str, float]:
    if cfg is None:
        cfg = default_config()
    pieces, heights = pack_skills(cfg.skills, cfg.board_columns, cfg.seed)
    return generate(pieces, heights, cfg)


class TestSVGStructure:
    def test_valid_xml(self):
        svg, _ = _make_svg()
        ET.fromstring(svg)

    def test_has_title(self):
        svg, _ = _make_svg()
        root = ET.fromstring(svg)
        ns = "{http://www.w3.org/2000/svg}"
        title = root.find(f"{ns}title")
        assert title is not None
        assert title.text == "STACK"

    def test_has_desc(self):
        svg, _ = _make_svg()
        root = ET.fromstring(svg)
        ns = "{http://www.w3.org/2000/svg}"
        desc = root.find(f"{ns}desc")
        assert desc is not None
        assert "PYTHON" in desc.text

    def test_role_img(self):
        svg, _ = _make_svg()
        root = ET.fromstring(svg)
        assert root.get("role") == "img"

    def test_aria_label(self):
        svg, _ = _make_svg()
        root = ET.fromstring(svg)
        assert root.get("aria-label") is not None
        assert "Falling-block" in root.get("aria-label")


class TestNoExternalResources:
    def test_no_xlink(self):
        svg, _ = _make_svg()
        assert "xlink:href" not in svg

    def test_no_script(self):
        svg, _ = _make_svg()
        assert "<script" not in svg

    def test_no_use(self):
        svg, _ = _make_svg()
        assert "<use " not in svg

    def test_no_external_urls(self):
        svg, _ = _make_svg()
        lines = svg.split("\n")
        for line in lines:
            if "xmlns" in line:
                continue
            assert "https://" not in line
            assert "http://" not in line


class TestReducedMotion:
    def test_prefers_reduced_motion(self):
        svg, _ = _make_svg()
        assert "prefers-reduced-motion" in svg
        assert "animation:none!important" in svg


class TestAnimationTiming:
    def test_positive_duration(self):
        _, duration = _make_svg()
        assert duration > 0

    def test_keyframes_present(self):
        svg, _ = _make_svg()
        assert "@keyframes f0" in svg
        assert "@keyframes f23" in svg

    def test_all_pieces_animated(self):
        svg, _ = _make_svg()
        for i in range(24):
            assert f"@keyframes f{i}" in svg


class TestCustomConfig:
    def test_custom_title(self):
        cfg = default_config()
        cfg.title = "MY TOOLS"
        svg, _ = _make_svg(cfg)
        assert "MY TOOLS" in svg

    def test_small_skill_set(self):
        skills = [
            SkillEntry(label="PYTHON", color="#3776ab", icon="python"),
            SkillEntry(label="REACT", color="#61dafb", icon="react"),
        ]
        cfg = Config(skills=skills, board_columns=6)
        svg, _ = _make_svg(cfg)
        assert "PYTHON" in svg
        assert "REACT" in svg

    def test_xml_escape_in_title(self):
        cfg = default_config()
        cfg.title = "A & B <tools>"
        svg, _ = _make_svg(cfg)
        assert "A &amp; B &lt;tools&gt;" in svg
        ET.fromstring(svg)
