"""Load the YAML configuration and resolve project paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "config.yaml"


@dataclass(frozen=True)
class Config:
    """Thin wrapper that keeps the raw settings and exposes resolved paths."""

    settings: dict[str, Any]

    def __getitem__(self, section: str) -> dict[str, Any]:
        return self.settings[section]

    def path(self, name: str) -> Path:
        """Return a configured directory as an absolute path."""
        return PROJECT_ROOT / self.settings["paths"][name]


def load_config(path: Path | str = DEFAULT_CONFIG) -> Config:
    """Read the configuration file."""
    with open(path, encoding="utf-8") as handle:
        return Config(yaml.safe_load(handle))
