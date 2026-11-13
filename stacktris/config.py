"""Configuration loading and validation for Stacktris."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .icons import SUPPORTED_TECHS

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass
class SkillEntry:
    """One skill to place on the board."""

    label: str
    color: str
    icon: str

    def __post_init__(self) -> None:
        if not self.label or not self.label.strip():
            raise ValueError("skill label must be non-empty")
        if not _HEX_RE.match(self.color):
            raise ValueError(f"invalid hex colour {self.color!r} for {self.label!r}")


@dataclass
class Config:
    """Full generator configuration."""

    skills: list[SkillEntry]
    cell_size: int = 56
    board_columns: int = 14
    step: float = 0.07
    stagger: float = 0.22
    wave_pause: float = 0.22
    start_delay: float = 0.4
    hold: float = 0.6
    seed: int = 11
    title: str = "STACK"
    background: str = "#0d1117"
    grid_color: str = "#141b33"
    separator_color: str = "#2a3558"
    border_color: str = "#050814"

    def __post_init__(self) -> None:
        if not self.skills:
            raise ValueError("at least one skill is required")
        if self.cell_size < 10:
            raise ValueError("cell_size must be >= 10")
        if self.board_columns < 2:
            raise ValueError("board_columns must be >= 2")
        if self.step <= 0:
            raise ValueError("step must be > 0")
        if self.stagger < 0:
            raise ValueError("stagger must be >= 0")
        if self.start_delay < 0:
            raise ValueError("start_delay must be >= 0")
        if self.hold < 0:
            raise ValueError("hold must be >= 0")
        for attr in ("background", "grid_color", "separator_color", "border_color"):
            val = getattr(self, attr)
            if not _HEX_RE.match(val):
                raise ValueError(f"invalid hex colour {val!r} for {attr}")


def default_config() -> Config:
    """The demo configuration matching the reference stack.svg."""
    demo_order = [
        "VERCEL", "DOCKER", "GITHUB ACTIONS", "PRISMA", "SQLITE", "VITEST",
        "PLAYWRIGHT", "TYPST", "LANGCHAIN", "LANGGRAPH", "OLLAMA", "FASTAPI",
        "PYTORCH", "MEDIAPIPE", "NODE.JS", "TAILWIND", "REACT", "NEXT.JS",
        "HTML/CSS", "JAVA", "SWIFT", "JAVASCRIPT", "TYPESCRIPT", "PYTHON",
    ]
    skills = []
    for name in demo_order:
        color, icon = SUPPORTED_TECHS[name]
        skills.append(SkillEntry(label=name, color=color, icon=icon))
    return Config(skills=skills)


def _resolve_skill(raw: dict[str, Any]) -> SkillEntry:
    """Resolve a skill dict, looking up defaults from SUPPORTED_TECHS when needed."""
    label = raw.get("label", "").strip().upper()
    if not label:
        raise ValueError(f"skill entry missing 'label': {raw}")
    defaults = SUPPORTED_TECHS.get(label)
    color = raw.get("color") or (defaults[0] if defaults else None)
    icon = raw.get("icon") or (defaults[1] if defaults else None)
    if not color:
        raise ValueError(
            f"skill {label!r} is not built-in — you must supply 'color'"
        )
    if not icon:
        raise ValueError(
            f"skill {label!r} is not built-in — you must supply 'icon' "
            f"(one of: {', '.join(sorted(SUPPORTED_TECHS))})"
        )
    return SkillEntry(label=label, color=color, icon=icon)


def load_config(path: str | Path) -> Config:
    """Load a JSON configuration file."""
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("config root must be a JSON object")
    skills_raw = data.get("skills")
    if skills_raw is None:
        raise ValueError("config must contain a 'skills' list")
    if not isinstance(skills_raw, list) or not skills_raw:
        raise ValueError("'skills' must be a non-empty list")
    skills = [_resolve_skill(s) for s in skills_raw]
    kwargs: dict[str, Any] = {"skills": skills}
    for key in (
        "cell_size", "board_columns", "step", "stagger", "wave_pause",
        "start_delay", "hold", "seed", "title", "background", "grid_color",
        "separator_color", "border_color",
    ):
        if key in data:
            kwargs[key] = data[key]
    return Config(**kwargs)
