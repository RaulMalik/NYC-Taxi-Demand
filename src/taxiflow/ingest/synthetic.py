"""Deterministic synthetic trip generator used for offline runs and tests.

Produces parquet files with the same column names as the real TLC feed so the
rest of the pipeline is identical whether data is live or synthetic.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..config import Settings
from .tlc import raw_path

log = logging.getLogger("taxiflow.ingest")

_PREFIX = {"yellow": "tpep", "green": "lpep"}
_HOUR_WEIGHT = np.array(
    [3, 2, 1, 1, 1, 2, 4, 7, 9, 7, 6, 6, 7, 7, 7, 8, 9, 11, 11, 10, 8, 7, 6, 4], dtype=float
)


def _month_bounds(month: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.Timestamp(month + "-01")
    return start, start + pd.offsets.MonthBegin(1)


def generate_fleet_month(fleet: str, month: str, n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start, end = _month_bounds(month)
    total_hours = int((end - start) / pd.Timedelta(hours=1))

    days = np.arange(total_hours) // 24
    weekday = (start.dayofweek + days) % 7
    hour = np.arange(total_hours) % 24
    weight = _HOUR_WEIGHT[hour] * np.where(weekday >= 5, 0.7, 1.0)
    weight = weight / weight.sum()

    slot = rng.choice(total_hours, size=n, p=weight)
    offset = rng.integers(0, 3600, size=n)
    pickup = start + pd.to_timedelta(slot * 3600 + offset, unit="s")

    distance = np.round(rng.lognormal(mean=0.9, sigma=0.6, size=n), 2)
    speed_mph = rng.normal(12, 3, size=n).clip(3, 45)
    duration_h = distance / speed_mph
    dropoff = pickup + pd.to_timedelta((duration_h * 3600).clip(60), unit="s")

    fare = np.round(3.0 + distance * 2.6 + duration_h * 26 + rng.normal(0, 1.5, size=n), 2)
    fare = fare.clip(2.5, None)
    tip = np.round(np.where(rng.random(n) < 0.6, fare * rng.uniform(0.1, 0.3, size=n), 0), 2)
    total = np.round(fare + tip + 1.0, 2)

    zones = rng.integers(1, 264, size=(n, 2))
    pax = rng.integers(1, 5, size=n)

    # a small, intentional band of anomalies for the anomaly stage to catch
    bad = rng.random(n) < 0.01
    fare[bad] = rng.choice([-5.0, 0.0, 480.0], size=bad.sum())
    distance[bad] = rng.choice([0.0, 95.0], size=bad.sum())

    df = pd.DataFrame(
        {
            f"{_PREFIX[fleet]}_pickup_datetime": pickup,
            f"{_PREFIX[fleet]}_dropoff_datetime": dropoff,
            "passenger_count": pax.astype("float64"),
            "trip_distance": distance,
            "PULocationID": zones[:, 0],
            "DOLocationID": zones[:, 1],
            "payment_type": rng.integers(1, 5, size=n),
            "fare_amount": fare,
            "tip_amount": tip,
            "total_amount": total,
        }
    )
    return df


def ingest_synthetic(settings: Settings, rows_per_file: int = 60_000) -> list[dict]:
    cfg = settings.ingest
    manifest = []
    for fi, fleet in enumerate(cfg.fleets):
        for mi, month in enumerate(cfg.months):
            n = rows_per_file if fleet == "yellow" else rows_per_file // 3
            df = generate_fleet_month(fleet, month, n=n, seed=1000 * fi + mi + 7)
            dest = raw_path(fleet, month)
            dest.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(dest, index=False)
            log.info("synthetic %s rows=%d -> %s", fleet, len(df), dest.name)
            manifest.append({"fleet": fleet, "month": month, "path": str(dest), "source": "synthetic"})
    return manifest
