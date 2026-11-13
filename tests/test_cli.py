"""Tests for the Stacktris CLI."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def run_cli(*args: str, expect_fail: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-m", "stacktris", *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if not expect_fail:
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
    return result


class TestCLIHelp:
    def test_help_flag(self):
        r = run_cli("--help")
        assert "Generate falling-block" in r.stdout
        assert "--output" in r.stdout
        assert "--config" in r.stdout
        assert "--skills" in r.stdout
        assert "--seed" in r.stdout

    def test_version_flag(self):
        r = run_cli("--version")
        assert "stacktris" in r.stdout
        assert "1.0.0" in r.stdout


class TestCLIListSkills:
    def test_list_skills(self):
        r = run_cli("--list-skills")
        assert "PYTHON" in r.stdout
        assert "REACT" in r.stdout
        assert "TYPESCRIPT" in r.stdout
        assert "#3776ab" in r.stdout


class TestCLIDefault:
    def test_default_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "test.svg")
            r = run_cli("-o", out)
            assert "wrote" in r.stdout
            svg = Path(out).read_text()
            assert svg.startswith("<svg")
            assert "</svg>" in svg
            assert 'class="p"' in svg

    def test_default_reproducibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            out1 = os.path.join(tmp, "a.svg")
            out2 = os.path.join(tmp, "b.svg")
            run_cli("-o", out1)
            run_cli("-o", out2)
            assert Path(out1).read_text() == Path(out2).read_text()

    def test_different_seed_produces_different_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out1 = os.path.join(tmp, "a.svg")
            out2 = os.path.join(tmp, "b.svg")
            run_cli("-o", out1, "--seed", "1")
            run_cli("-o", out2, "--seed", "2")
            assert Path(out1).read_text() != Path(out2).read_text()


class TestCLICustomSkills:
    def test_valid_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "test.svg")
            r = run_cli("--skills", "Python", "React", "-o", out, "--columns", "6")
            assert "wrote" in r.stdout
            svg = Path(out).read_text()
            assert "PYTHON" in svg
            assert "REACT" in svg

    def test_invalid_skill(self):
        r = run_cli("--skills", "NotARealSkill", expect_fail=True)
        assert r.returncode == 1
        assert "unknown skill" in r.stderr


class TestCLIConfig:
    def test_config_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = os.path.join(tmp, "cfg.json")
            out = os.path.join(tmp, "test.svg")
            Path(cfg).write_text(
                '{"skills": [{"label": "Python"}, {"label": "Docker"}], "board_columns": 6}'
            )
            r = run_cli("-c", cfg, "-o", out)
            assert "wrote" in r.stdout

    def test_missing_config(self):
        r = run_cli("-c", "/nonexistent.json", expect_fail=True)
        assert r.returncode == 1

    def test_invalid_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = os.path.join(tmp, "bad.json")
            Path(cfg).write_text('{"skills": []}')
            r = run_cli("-c", cfg, expect_fail=True)
            assert r.returncode == 1
            assert "non-empty" in r.stderr


class TestCLILineClear:
    def test_default_has_line_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "test.svg")
            run_cli("-o", out)
            svg = Path(out).read_text()
            assert "lc-flash" in svg
            assert "@keyframes a0" in svg

    def test_no_line_clear_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "test.svg")
            run_cli("-o", out, "--no-line-clear")
            svg = Path(out).read_text()
            assert "lc-flash" not in svg
            assert "@keyframes a0" not in svg

    def test_no_line_clear_with_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "cfg.json")
            out = os.path.join(tmp, "test.svg")
            Path(cfg_path).write_text(
                '{"skills": [{"label": "Python"}, {"label": "Docker"}], "board_columns": 6}'
            )
            run_cli("-c", cfg_path, "-o", out, "--no-line-clear")
            svg = Path(out).read_text()
            assert "lc-flash" not in svg

    def test_default_loops_and_no_loop_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_loop = os.path.join(tmp, "loop.svg")
            out_once = os.path.join(tmp, "once.svg")
            run_cli("-o", out_loop)
            run_cli("-o", out_once, "--no-loop")
            assert "linear infinite" in Path(out_loop).read_text()
            assert "linear 1 both" in Path(out_once).read_text()
            assert "linear infinite" not in Path(out_once).read_text()
