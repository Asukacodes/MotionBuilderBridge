#!/usr/bin/env python3
"""Skill wrapper for the repository-level MotionBuilderBridge CLI."""

import os
import runpy
import sys
from pathlib import Path


def _resolve_root() -> Path:
    env_root = os.environ.get("MOTIONBUILDER_BRIDGE_HOME")
    if env_root:
        root = Path(env_root).expanduser()
        if (root / "scripts" / "bridge.py").is_file():
            return root

    here = Path(__file__).resolve()
    config_file = here.parents[1] / "bridge_home.txt"
    if config_file.is_file():
        root_text = config_file.read_text(encoding="utf-8-sig").strip()
        root = Path(root_text).expanduser()
        if (root / "scripts" / "bridge.py").is_file():
            return root

    # Repo-local layout: <repo>/.claude/skills/motionbuilder-bridge/scripts/bridge.py
    root = here.parents[4]
    if (root / "scripts" / "bridge.py").is_file():
        return root

    raise SystemExit(
        "MotionBuilderBridge root not found. Set MOTIONBUILDER_BRIDGE_HOME "
        "or run tools/install_agent_skill.ps1 from the repository."
    )


ROOT = _resolve_root()
CLI = ROOT / "scripts" / "bridge.py"

sys.path.insert(0, str(CLI.parent))
runpy.run_path(str(CLI), run_name="__main__")
