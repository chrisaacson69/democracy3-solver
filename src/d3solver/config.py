"""Resolve the Democracy 3 data directory (machine-specific, so kept out of git)."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def sim_dir() -> Path:
    """Return the simulation-data directory.

    Resolution order: ``D3_SIM_DIR`` env var → ``config.toml`` at the repo root. Raises if neither
    is set, rather than guessing an install path.
    """
    env = os.environ.get("D3_SIM_DIR")
    if env:
        return Path(env)
    cfg = _REPO_ROOT / "config.toml"
    if cfg.exists():
        data = tomllib.loads(cfg.read_text(encoding="utf-8"))
        d = data.get("data", {}).get("sim_dir")
        if d:
            return Path(d)
    raise RuntimeError(
        "No data dir configured. Set D3_SIM_DIR or copy config.example.toml to config.toml."
    )


__all__ = ["sim_dir"]
