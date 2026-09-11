"""CCRA pipeline entry point.

Usage:
    python -m ccra.pipeline all
    python -m ccra.pipeline ingest simulate load quality export
    python -m ccra.pipeline all --config config/pipeline.ci.yml

Stages are idempotent and individually runnable, so a failure can be resumed
from the stage that broke rather than from the top.
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable

import pandas as pd

from ccra.config import load_config
from ccra.logging_setup import get_logger

log = get_logger("ccra.pipeline")

STAGE_ORDER = ["ingest", "simulate", "load", "quality", "export"]


def _stage_ingest(cfg, ctx: dict) -> None:
    from ccra.ingest import macro
    ctx["macro"] = macro.run(cfg)


def _stage_simulate(cfg, ctx: dict) -> None:
    from ccra.simulate import portfolio
    macro_df = ctx.get("macro")
    if macro_df is None:
        macro_df = pd.read_parquet(cfg.path("raw") / "macro.parquet")
    ctx.update(portfolio.run(cfg, macro_df))


def _stage_load(cfg, ctx: dict) -> None:
    from ccra.warehouse import load
    ctx["load_counts"] = load.run(cfg)


def _stage_quality(cfg, ctx: dict) -> None:
    from ccra.quality import checks
    ctx["quality"] = checks.run(cfg)


def _stage_export(cfg, ctx: dict) -> None:
    from ccra.export import powerbi
    ctx["exports"] = powerbi.run(cfg)


STAGES: dict[str, Callable] = {
    "ingest": _stage_ingest,
    "simulate": _stage_simulate,
    "load": _stage_load,
    "quality": _stage_quality,
    "export": _stage_export,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ccra", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "stages", nargs="+",
        help="stages to run, in order, or 'all' for the full pipeline: "
             + ", ".join(STAGE_ORDER),
    )
    parser.add_argument("--config", default=None, help="path to pipeline.yml")
    args = parser.parse_args(argv)

    requested = STAGE_ORDER if "all" in args.stages else args.stages
    unknown = [s for s in requested if s not in STAGES]
    if unknown:
        parser.error(f"unknown stage(s): {', '.join(unknown)}. Valid: {', '.join(STAGE_ORDER)}")

    cfg = load_config(args.config)
    log.info("CCRA pipeline | config=%s | stages=%s", cfg.source_path, " -> ".join(requested))

    ctx: dict = {}
    for name in requested:
        STAGES[name](cfg, ctx)

    log.info("Pipeline complete: %s", " -> ".join(requested))
    return 0


if __name__ == "__main__":
    sys.exit(main())
