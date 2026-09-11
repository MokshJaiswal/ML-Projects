"""Configuration loading for the CCRA pipeline.

Every stage reads its parameters from ``config/pipeline.yml`` so that a run is
fully described by that one file plus the git SHA. Nothing is hard-coded in the
stage modules.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "pipeline.yml"


class ConfigError(RuntimeError):
    """Raised when the configuration is missing or internally inconsistent."""


@dataclass(frozen=True)
class Config:
    """Parsed pipeline configuration with convenience accessors."""

    raw: dict[str, Any]
    source_path: Path

    # -- section accessors -------------------------------------------------
    @property
    def paths(self) -> dict[str, str]:
        return self.raw["paths"]

    @property
    def window(self) -> dict[str, str]:
        return self.raw["window"]

    @property
    def macro(self) -> dict[str, Any]:
        return self.raw["macro"]

    @property
    def portfolio(self) -> dict[str, Any]:
        return self.raw["portfolio"]

    @property
    def risk(self) -> dict[str, Any]:
        return self.raw["risk"]

    @property
    def quality(self) -> dict[str, Any]:
        return self.raw["quality"]

    # -- path helpers ------------------------------------------------------
    def path(self, key: str) -> Path:
        """Resolve a configured path against the repo root and create parents."""
        p = REPO_ROOT / self.paths[key]
        target_dir = p.parent if p.suffix else p
        target_dir.mkdir(parents=True, exist_ok=True)
        return p

    def validate(self) -> None:
        """Fail fast on the configuration mistakes that silently corrupt a run."""
        mix = self.portfolio["product_mix"]
        total = sum(mix.values())
        if abs(total - 1.0) > 1e-6:
            raise ConfigError(
                f"portfolio.product_mix must sum to 1.0, got {total:.6f}"
            )

        region_share = sum(r["share"] for r in self.portfolio["regions"].values())
        if abs(region_share - 1.0) > 1e-6:
            raise ConfigError(
                f"portfolio.regions shares must sum to 1.0, got {region_share:.6f}"
            )

        start = self.window["observation_start"]
        end = self.window["observation_end"]
        if start >= end:
            raise ConfigError(
                f"window.observation_start ({start}) must precede observation_end ({end})"
            )

        products = set(mix)
        for section in ("product_intercept", "loss_given_default"):
            missing = products - set(self.risk[section])
            if missing:
                raise ConfigError(f"risk.{section} is missing products: {sorted(missing)}")


def load_config(path: str | Path | None = None) -> Config:
    """Load and validate the pipeline configuration.

    The path may be overridden with the ``CCRA_CONFIG`` environment variable,
    which is how the GitHub Actions workflow points at a smaller CI profile.
    """
    resolved = Path(path or os.environ.get("CCRA_CONFIG") or DEFAULT_CONFIG)
    if not resolved.exists():
        raise ConfigError(f"configuration file not found: {resolved}")

    with resolved.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    cfg = Config(raw=raw, source_path=resolved)
    cfg.validate()
    return cfg
