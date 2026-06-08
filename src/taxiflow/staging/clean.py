"""Normalize raw yellow/green parquet into one cleaned, typed trip table."""
from __future__ import annotations

import logging

import duckdb

from ..config import PATHS, Settings
from ..ingest.tlc import raw_path

log = logging.getLogger("taxiflow.staging")

STAGED_PATH = PATHS.staged / "trips.parquet"
_PREFIX = {"yellow": "tpep", "green": "lpep"}


def _fleet_select(fleet: str, path: str, sample_rows: int | None) -> str:
    prefix = _PREFIX[fleet]
    limit = f"LIMIT {sample_rows}" if sample_rows else ""
    return f"""
        SELECT
            '{fleet}' AS fleet,
            {prefix}_pickup_datetime  AS pickup_datetime,
            {prefix}_dropoff_datetime AS dropoff_datetime,
            CAST(PULocationID AS INTEGER) AS pickup_location_id,
            CAST(DOLocationID AS INTEGER) AS dropoff_location_id,
            CAST(passenger_count AS DOUBLE) AS passenger_count,
            CAST(trip_distance AS DOUBLE) AS trip_distance,
            CAST(fare_amount AS DOUBLE) AS fare_amount,
            CAST(tip_amount AS DOUBLE) AS tip_amount,
            CAST(total_amount AS DOUBLE) AS total_amount,
            CAST(payment_type AS INTEGER) AS payment_type
        FROM read_parquet('{path}')
        {limit}
    """


def _build_query(selects: list[str], settings: Settings) -> str:
    c, w = settings.cleaning, settings.window
    union = "\n        UNION ALL\n".join(selects)
    return f"""
    WITH raw AS (
        {union}
    ),
    feat AS (
        SELECT
            *,
            CAST(pickup_datetime AS DATE) AS pickup_date,
            EXTRACT(hour FROM pickup_datetime) AS pickup_hour,
            isodow(pickup_datetime) - 1 AS pickup_weekday,
            dayname(pickup_datetime) AS pickup_day_name,
            isodow(pickup_datetime) IN (6, 7) AS is_weekend,
            EXTRACT(hour FROM pickup_datetime) IN (7, 8, 9, 16, 17, 18, 19) AS is_rush_hour,
            (epoch(dropoff_datetime) - epoch(pickup_datetime)) / 60.0 AS trip_duration_min
        FROM raw
    )
    SELECT
        *,
        trip_distance / NULLIF(trip_duration_min / 60.0, 0) AS avg_speed_mph
    FROM feat
    WHERE pickup_datetime >= TIMESTAMP '{w.start}'
      AND pickup_datetime <  TIMESTAMP '{w.end}'
      AND dropoff_datetime > pickup_datetime
      AND fare_amount BETWEEN {c.min_fare} AND {c.max_fare}
      AND trip_distance BETWEEN {c.min_distance} AND {c.max_distance}
      AND trip_duration_min BETWEEN {c.min_duration_min} AND {c.max_duration_min}
      AND coalesce(passenger_count, 1) BETWEEN 1 AND {c.max_passengers}
    """


def run_staging(settings: Settings) -> dict:
    PATHS.staged.mkdir(parents=True, exist_ok=True)
    selects = []
    for fleet in settings.ingest.fleets:
        for month in settings.ingest.months:
            path = raw_path(fleet, month)
            if path.exists():
                selects.append(_fleet_select(fleet, str(path), settings.ingest.sample_rows))
            else:
                log.warning("missing raw file %s", path.name)
    if not selects:
        raise FileNotFoundError("no raw files found; run ingest first")

    con = duckdb.connect()
    query = _build_query(selects, settings)
    raw_total = con.execute(
        "SELECT count(*) FROM (" + "\n UNION ALL \n".join(selects) + ")"
    ).fetchone()[0]
    con.execute(
        f"COPY ({query}) TO '{STAGED_PATH}' (FORMAT PARQUET)"
    )
    kept = con.execute(f"SELECT count(*) FROM read_parquet('{STAGED_PATH}')").fetchone()[0]
    con.close()

    summary = {
        "rows_raw": int(raw_total),
        "rows_clean": int(kept),
        "rows_removed": int(raw_total - kept),
        "removed_pct": round((raw_total - kept) / raw_total * 100, 2) if raw_total else 0.0,
        "path": str(STAGED_PATH),
    }
    log.info("staged %d/%d rows kept (%.1f%% removed)",
             summary["rows_clean"], summary["rows_raw"], summary["removed_pct"])
    return summary
