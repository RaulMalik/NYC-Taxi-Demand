"""Run the data contract on a sample and full-table metrics on the lot."""
from __future__ import annotations

import json
import logging

import duckdb

from ..config import PATHS, Settings
from ..staging.clean import STAGED_PATH
from .schemas import trips_schema

log = logging.getLogger("taxiflow.quality")

_KEY_COLS = ["trip_distance", "fare_amount", "tip_amount", "total_amount",
             "trip_duration_min", "avg_speed_mph"]


def _full_table_metrics(con: duckdb.DuckDBPyConnection, src: str) -> dict:
    total = con.execute(f"SELECT count(*) FROM {src}").fetchone()[0]
    null_rates = {}
    for col in ["passenger_count", "pickup_location_id", "dropoff_location_id", *_KEY_COLS]:
        nulls = con.execute(f"SELECT count(*) - count({col}) FROM {src}").fetchone()[0]
        null_rates[col] = round(nulls / total, 4) if total else 0.0
    ranges = {}
    for col in _KEY_COLS:
        lo, hi = con.execute(f"SELECT min({col}), max({col}) FROM {src}").fetchone()
        ranges[col] = {"min": lo, "max": hi}
    dup = con.execute(
        f"""SELECT count(*) FROM (
                SELECT fleet, pickup_datetime, pickup_location_id, dropoff_location_id,
                       fare_amount, count(*) c
                FROM {src}
                GROUP BY ALL HAVING count(*) > 1)"""
    ).fetchone()[0]
    dmin, dmax = con.execute(f"SELECT min(pickup_date), max(pickup_date) FROM {src}").fetchone()
    return {
        "row_count": int(total),
        "duplicate_groups": int(dup),
        "date_min": str(dmin),
        "date_max": str(dmax),
        "null_rates": null_rates,
        "ranges": {k: {kk: float(vv) for kk, vv in v.items()} for k, v in ranges.items()},
    }


def run_quality(settings: Settings, sample_rows: int = 200_000) -> dict:
    PATHS.quality.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    src = f"read_parquet('{STAGED_PATH}')"

    metrics = _full_table_metrics(con, src)
    sample = con.execute(f"SELECT * FROM {src} USING SAMPLE {sample_rows} ROWS").df()
    con.close()

    schema = trips_schema(settings)
    contract = {"sample_rows": len(sample), "passed": True, "errors": []}
    try:
        schema.validate(sample, lazy=True)
    except Exception as exc:
        contract["passed"] = False
        failures = getattr(exc, "failure_cases", None)
        if failures is not None:
            contract["errors"] = (
                failures.groupby("check").size().reset_index(name="n").to_dict("records")
            )
        else:
            contract["errors"] = [{"check": str(exc)[:300]}]

    report = {
        "status": "pass" if contract["passed"] else "fail",
        "metrics": metrics,
        "contract": contract,
    }
    (PATHS.quality / "trips_quality.json").write_text(json.dumps(report, indent=2, default=str))
    (PATHS.quality / "trips_quality.md").write_text(_to_markdown(report))
    log.info("data quality: %s | rows=%s dups=%s",
             report["status"], metrics["row_count"], metrics["duplicate_groups"])
    return report


def _to_markdown(report: dict) -> str:
    m = report["metrics"]
    lines = [
        "# Trips data-quality report",
        "",
        f"**Status:** {report['status'].upper()}",
        f"**Rows:** {m['row_count']:,}  |  **Duplicate groups:** {m['duplicate_groups']:,}",
        f"**Date range:** {m['date_min']} → {m['date_max']}",
        "",
        "## Null rates",
        "| column | null rate |",
        "| --- | --- |",
    ]
    lines += [f"| {c} | {r:.2%} |" for c, r in m["null_rates"].items()]
    lines += ["", "## Ranges", "| column | min | max |", "| --- | --- | --- |"]
    lines += [f"| {c} | {v['min']:.2f} | {v['max']:.2f} |" for c, v in m["ranges"].items()]
    contract = report["contract"]
    lines += ["", "## Contract (pandera)", f"- sample rows: {contract['sample_rows']:,}",
              f"- passed: {contract['passed']}"]
    if contract["errors"]:
        lines += ["- failing checks:"] + [f"  - {e}" for e in contract["errors"]]
    return "\n".join(lines) + "\n"
