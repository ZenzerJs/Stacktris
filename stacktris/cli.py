"""Command-line interface for Stacktris."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import Config, SkillEntry, default_config, load_config
from .generator import generate
from .icons import SUPPORTED_TECHS
from .layout import pack_skills


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stacktris",
        description="Generate falling-block tech-stack SVG graphics.",
    )
    p.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    p.add_argument(
        "-o", "--output",
        default="stack.svg",
        help="output SVG path (default: stack.svg)",
    )
    p.add_argument(
        "-c", "--config",
        help="JSON config file (overrides --skills and animation flags)",
    )
    p.add_argument(
        "--skills",
        nargs="+",
        metavar="SKILL",
        help="space-separated skill names (built-in names only when no config)",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=11,
        help="random seed for layout and wave ordering (default: 11)",
    )
    p.add_argument(
        "--columns",
        type=int,
        default=14,
        help="board width in columns (default: 14)",
    )
    p.add_argument(
        "--cell-size",
        type=int,
        default=56,
        help="cell size in pixels (default: 56)",
    )
    p.add_argument(
        "--step",
        type=float,
        default=0.07,
        help="seconds per row drop tick (default: 0.07)",
    )
    p.add_argument(
        "--stagger",
        type=float,
        default=0.22,
        help="delay between pieces in a wave (default: 0.22)",
    )
    p.add_argument(
        "--title",
        default="STACK",
        help="title text shown at top of graphic (default: STACK)",
    )
    p.add_argument(
        "--list-skills",
        action="store_true",
        help="print supported built-in skill names and exit",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.list_skills:
        for name, (color, icon) in sorted(SUPPORTED_TECHS.items()):
            print(f"  {name:<20s} {color}  ({icon})")
        return 0

    if args.config:
        try:
            cfg = load_config(args.config)
        except (ValueError, FileNotFoundError, KeyError) as e:
            print(f"error: config: {e}", file=sys.stderr)
            return 1
    elif args.skills:
        skills: list[SkillEntry] = []
        for name in args.skills:
            key = name.upper()
            if key not in SUPPORTED_TECHS:
                print(
                    f"error: unknown skill {name!r}. "
                    f"Use --list-skills to see available names.",
                    file=sys.stderr,
                )
                return 1
            color, icon = SUPPORTED_TECHS[key]
            skills.append(SkillEntry(label=key, color=color, icon=icon))
        cfg = Config(
            skills=skills,
            seed=args.seed,
            board_columns=args.columns,
            cell_size=args.cell_size,
            step=args.step,
            stagger=args.stagger,
            title=args.title,
        )
    else:
        cfg = default_config()
        cfg.seed = args.seed
        cfg.board_columns = args.columns
        cfg.cell_size = args.cell_size
        cfg.step = args.step
        cfg.stagger = args.stagger
        cfg.title = args.title

    try:
        pieces, heights = pack_skills(cfg.skills, cfg.board_columns, cfg.seed)
    except ValueError as e:
        print(f"error: layout: {e}", file=sys.stderr)
        return 1

    try:
        svg, duration = generate(pieces, heights, cfg)
    except ValueError as e:
        print(f"error: generate: {e}", file=sys.stderr)
        return 1

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    print(f"wrote {out} ({len(svg):,} bytes), animation ~{duration:.1f}s")
    return 0
