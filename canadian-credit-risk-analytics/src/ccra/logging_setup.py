"""Structured logging shared by every pipeline stage.

Each stage logs a start/finish pair with row counts and elapsed time so that a
scheduled run leaves an auditable trail — the same expectation a bank places on
a production reporting job.
"""

from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from typing import Iterator

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-22s | %(message)s"
_configured = False


def get_logger(name: str) -> logging.Logger:
    """Return a logger, configuring the root handler exactly once."""
    global _configured
    if not _configured:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
        root = logging.getLogger()
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        _configured = True
    return logging.getLogger(name)


@contextmanager
def stage(logger: logging.Logger, name: str) -> Iterator[dict]:
    """Time a pipeline stage and log its outcome.

    Yields a mutable dict; anything placed in it is reported on completion:

        with stage(log, "ingest_macro") as st:
            st["rows"] = len(df)
    """
    logger.info("START  %s", name)
    started = time.perf_counter()
    metrics: dict = {}
    try:
        yield metrics
    except Exception:
        elapsed = time.perf_counter() - started
        logger.exception("FAILED %s after %.2fs", name, elapsed)
        raise
    elapsed = time.perf_counter() - started
    detail = " ".join(f"{k}={v}" for k, v in metrics.items())
    logger.info("DONE   %s in %.2fs %s", name, elapsed, detail)
