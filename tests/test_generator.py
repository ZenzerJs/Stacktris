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


class TestLineClear:
    def test_valid_xml_with_line_clear(self):
        svg, _ = _make_svg()
        ET.fromstring(svg)

    def test_extra_column_added(self):
        cfg = default_config()
        svg, _ = _make_svg(cfg)
        root = ET.fromstring(svg)
        expected_w = 40 * 2 + (cfg.board_columns + 1) * cfg.cell_size
        assert root.get("width") == str(expected_w)

    def test_no_extra_column_when_disabled(self):
        cfg = default_config()
        cfg.line_clear = False
        svg, _ = _make_svg(cfg)
        root = ET.fromstring(svg)
        expected_w = 40 * 2 + cfg.board_columns * cfg.cell_size
        assert root.get("width") == str(expected_w)

    def test_ai_tool_keyframes_present(self):
        svg, _ = _make_svg()
        assert "@keyframes a0" in svg
        assert "@keyframes a1" in svg
        assert "@keyframes a2" in svg

    def test_flash_keyframe(self):
        svg, _ = _make_svg()
        assert "@keyframes lc-flash-s0" in svg
        assert "@keyframes lc-flash-s1" in svg

    def test_fade_keyframe(self):
        svg, _ = _make_svg()
        assert "@keyframes lc-fade-s0" in svg
        assert "@keyframes lc-fade-s1" in svg

    def test_drop_keyframe(self):
        svg, _ = _make_svg()
        assert "@keyframes lc-drop-" in svg

    def test_flash_rects_present(self):
        svg, _ = _make_svg()
        assert 'class="fl"' in svg

    def test_line_clear_inner_wrappers(self):
        svg, _ = _make_svg()
        assert 'class="lc"' in svg

    def test_ai_tools_in_description(self):
        svg, _ = _make_svg()
        assert "CURSOR" in svg
        assert "CLAUDE" in svg
        assert "ANTIGRAVITY" in svg

    def test_no_line_clear_elements_when_disabled(self):
        cfg = default_config()
        cfg.line_clear = False
        svg, _ = _make_svg(cfg)
        assert "lc-flash" not in svg
        assert "@keyframes a0" not in svg
        assert 'class="fl"' not in svg

    def test_longer_duration_with_line_clear(self):
        cfg_on = default_config()
        cfg_off = default_config()
        cfg_off.line_clear = False
        _, dur_on = _make_svg(cfg_on)
        _, dur_off = _make_svg(cfg_off)
        assert dur_on > dur_off

    def test_reduced_motion_covers_line_clear(self):
        svg, _ = _make_svg()
        assert ".lc" in svg
        assert ".fl" in svg
        assert "animation:none!important" in svg

    def test_small_set_with_line_clear(self):
        skills = [
            SkillEntry(label="PYTHON", color="#3776ab", icon="python"),
            SkillEntry(label="REACT", color="#61dafb", icon="react"),
        ]
        cfg = Config(skills=skills, board_columns=6, line_clear=True)
        svg, _ = _make_svg(cfg)
        ET.fromstring(svg)

    def test_partial_piece_surviving_cells_preserved(self):
        svg, _ = _make_svg()
        assert "@keyframes lc-appear-s0" in svg
        assert "@keyframes lc-appear-s1" in svg
        # Stage 0 cuts 5 pieces (LANGCHAIN, LANGGRAPH, OLLAMA, FASTAPI, PYTORCH);
        # Stage 1 cuts 4 pieces (JAVA, SWIFT, JAVASCRIPT, TYPESCRIPT).
        assert svg.count("animation:lc-appear-s0") >= 4
        assert svg.count("animation:lc-appear-s1") >= 4
        assert svg.count("animation:lc-drop-") >= 10

    def test_ai_pieces_drop_without_overtaking(self):
        import re

        svg, _ = _make_svg()
        # Each AI piece a{i} must start after a{i-1} finishes falling (and after its stage clears)
        end_times = []
        start_times = []
        for idx in range(3):
            block_start = svg.index(f"@keyframes a{idx}{{")
            depth = 0
            block_end = block_start
            for pos in range(block_start, len(svg)):
                if svg[pos] == "{":
                    depth += 1
                elif svg[pos] == "}":
                    depth -= 1
                    if depth == 0:
                        block_end = pos + 1
                        break
            block = svg[block_start:block_end]
            pcts = [float(x) for x in re.findall(r"(\d+\.\d+)%", block)]
            start_times.append(pcts[0])
            end_times.append(pcts[-1])
        assert start_times[1] > end_times[0]
        assert start_times[2] > end_times[1]

    def test_antigravity_l_shape_and_top_logos(self):
        from stacktris.config import default_config
        from stacktris.generator import _create_ai_pieces, _find_complete_rows, _label_and_icon
        from stacktris.layout import pack_skills

        cfg = default_config()
        pieces, heights = pack_skills(cfg.skills, cfg.board_columns, cfg.seed)
        max_h = max(heights)
        cr = _find_complete_rows(pieces, cfg.board_columns, max_h)
        ai = _create_ai_pieces(cfg.get_line_clear_skills(), cfg.board_columns, max_h, pieces, cr)
        assert ai[2].skill.label == "ANTIGRAVITY"
        assert ai[2].cells == [(12, 6), (13, 6), (14, 6), (14, 7)]

        # Surviving top pieces keep their logos in the upper rows (>= 6)
        for name in ("SWIFT", "JAVASCRIPT", "PYTHON", "TYPESCRIPT", "JAVA"):
            p = next(x for x in pieces if x.skill.label == name)
            _, _, _, _, icon_cell = _label_and_icon(
                p.skill.label, p.cells, "#fff", "#000", max_h, cfg.cell_size
            )
            assert icon_cell[1] >= 6, f"{name} icon landed on row {icon_cell[1]}"

        svg, _ = _make_svg(cfg)
        assert ">ANTIGRAVITY</text>" in svg
