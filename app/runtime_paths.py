"""Paths for state that must remain beside a packaged executable."""

import sys
from pathlib import Path


def application_directory() -> Path:
    """Return the folder containing persistent CafePOS files."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def logs_directory() -> Path:
    """Create and return the application log directory."""
    path = application_directory() / "logs"
    path.mkdir(exist_ok=True)
    return path
