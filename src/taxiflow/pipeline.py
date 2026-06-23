"""End-to-end pipeline runner with per-stage timing."""
from __future__ import annotations

import logging
import time

from .analytics import run_anomaly, run_forecast
from .bi import run_export
from .config import Settings, get_settings
from .ingest import run_ingest
from .logging_setup import setup_logging
from .quality import run_quality
from .staging import run_staging
from .viz import render_all
from .warehouse import run_warehouse

log = logging.getLogger("taxiflow.pipeline")

STAGES = [
    ("ingest", run_ingest),
    ("stage", run_staging),
    ("quality", run_quality),
    ("warehouse", run_warehouse),
    ("forecast", run_forecast),
    ("anomaly", run_anomaly),
    ("viz", render_all),
    ("export", run_export),
]


def run_all(settings: Settings | None = None) -> dict:
    setup_logging()
    settings = settings or get_settings()
    results = {}
    for name, fn in STAGES:
        start = time.perf_counter()
        log.info("[bold cyan]== stage: %s ==[/bold cyan]", name)
        results[name] = fn(settings)
        log.info("stage %s done in %.1fs", name, time.perf_counter() - start)
    return results
