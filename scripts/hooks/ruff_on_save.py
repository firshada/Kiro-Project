"""Kiro PostFileSave hook: ruff format, then ruff check --fix on the project."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUFF = ROOT / ".venv" / "Scripts" / "ruff.exe"


def main() -> int:
    subprocess.run([str(RUFF), "format", "."], cwd=ROOT, check=False)
    result = subprocess.run([str(RUFF), "check", "--fix", "."], cwd=ROOT, check=False)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
