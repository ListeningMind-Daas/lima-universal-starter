#!/usr/bin/env python3
"""다리 — 차트 CLI 정본은 `lima_agent/skills/lm-chart/scripts/viz.py` 다(2026-10-25). 받은 인자를 그대로 넘긴다."""
import subprocess, sys
from pathlib import Path

CANON = Path(__file__).resolve().parents[2] / "lm-chart/scripts/viz.py"
if __name__ == "__main__":
    raise SystemExit(subprocess.run([sys.executable, str(CANON), *sys.argv[1:]]).returncode)
