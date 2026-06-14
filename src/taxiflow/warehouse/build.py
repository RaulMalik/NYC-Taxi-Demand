"""Build the DuckDB star schema (dims + fact) and run the mart SQL files."""
from __future__ import annotations

import logging

from ..config import PATHS, Settings
from ..duck import connect
from ..ingest.zones import DIM_ZONE_PATH
from ..staging.clean import STAGED_PATH

log = logging.getLogger("taxiflow.warehouse")

DIMS = ["dim_date", "dim_fleet", "dim_time", "dim_zone"]
FACTS = ["fact_trip"]


def _build_dims_and_fact(con, settings: Settings) -> None:
    w = settings.window
    con.execute(f"CREATE OR REPLACE VIEW stg_trips AS SELECT * FROM read_parquet('{STAGED_PATH}')")
    con.execute(f"CREATE OR REPLACE TABLE dim_zone AS SELECT * FROM read_parquet('{DIM_ZONE_PATH}')")

    con.execute(f"""
        CREATE OR REPLACE TABLE dim_date AS
        WITH spine AS (
            SELECT CAST(d AS DATE) AS date
            FROM range(DATE '{w.start}', DATE '{w.end}', INTERVAL 1 DAY) t(d)
        )
        SELECT
            CAST(strftime(date, '%Y%m%d') AS INTEGER) AS date_key,
            date,
            EXTRACT(year FROM date) AS year,
            EXTRACT(month FROM date) AS month,
            monthname(date) AS month_name,
            EXTRACT(day FROM date) AS day,
            isodow(date) - 1 AS weekday,
            dayname(date) AS weekday_name,
            isodow(date) IN (6, 7) AS is_weekend,
            date_trunc('week', date) AS week_start
        FROM spine
    """)

    con.execute("""
        CREATE OR REPLACE TABLE dim_fleet AS
        SELECT * FROM (VALUES
            ('yellow', 'Yellow', '#F2A900'),
            ('green',  'Green',  '#2E7D32')
        ) t(fleet, fleet_name, color)
    """)

    con.execute("""
        CREATE OR REPLACE TABLE dim_time AS
        SELECT
            h AS hour,
            CASE WHEN h < 6 THEN 'Overnight' WHEN h < 10 THEN 'Morning'
                 WHEN h < 16 THEN 'Midday' WHEN h < 20 THEN 'Evening' ELSE 'Night' END AS day_part,
            h IN (7, 8, 9, 16, 17, 18, 19) AS is_rush_hour
        FROM range(0, 24) t(h)
    """)

    con.execute("""
        CREATE OR REPLACE TABLE fact_trip AS
        SELECT
            row_number() OVER () AS trip_id,
            CAST(strftime(pickup_date, '%Y%m%d') AS INTEGER) AS date_key,
            pickup_hour,
            fleet,
            pickup_location_id,
            dropoff_location_id,
            passenger_count, trip_distance, fare_amount, tip_amount, total_amount,
            trip_duration_min, avg_speed_mph, is_weekend, is_rush_hour
        FROM stg_trips
    """)


def run_warehouse(settings: Settings) -> dict:
    con = connect()
    _build_dims_and_fact(con, settings)

    mart_dir = PATHS.sql / "marts"
    marts = sorted(mart_dir.glob("*.sql"))
    for path in marts:
        con.execute(path.read_text())
        log.info("built %s", path.stem)

    tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}
    con.close()
    log.info("warehouse tables: %s", ", ".join(f"{k}={v}" for k, v in counts.items()))
    return {"tables": counts}
