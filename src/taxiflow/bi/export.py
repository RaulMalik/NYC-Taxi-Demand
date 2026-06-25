"""Export every warehouse table to CSV + Parquet for Tableau / Power BI."""
from __future__ import annotations

import json
import logging

from ..config import PATHS, Settings
from ..duck import connect

log = logging.getLogger("taxiflow.bi")

_GUIDE = """# Connecting Tableau / Power BI

Two equivalent options — both are produced by `taxiflow export`.

## Option A — DuckDB warehouse (single file, recommended)
`exports/warehouse.duckdb` holds the full star schema (`dim_*`, `fact_trip`, `mart_*`).
- **Power BI:** Get Data -> DuckDB connector (or ODBC) -> point at `exports/warehouse.duckdb`.
- **Tableau:** use the DuckDB JDBC/connector and open the same file.

## Option B — flat extracts (works everywhere)
`exports/bi/*.parquet` and `exports/bi/*.csv` — one file per table.
Connect with the native Parquet/CSV/folder connector in either tool.

## Suggested first views
- Map: `mart_zone_demand` (lat/lng) sized/coloured by `pickups`.
- Heatmap: `mart_hourly_volume` (weekday x hour) on `avg_rides_per_day`.
- Line: `mart_daily_volume` `rides` over `date`, split by `fleet`.
- Forecast: `mart_forecast` `y_actual` vs `yhat` with the `yhat_lower/upper` band.
- Flows: `mart_route_flows` pickup->dropoff lat/lng pairs.
"""


def run_export(settings: Settings, csv_row_limit: int = 1_000_000) -> dict:
    PATHS.bi.mkdir(parents=True, exist_ok=True)
    con = connect(read_only=True)
    tables = [r[0] for r in con.execute("SELECT table_name FROM duckdb_tables() ORDER BY 1").fetchall()]
    manifest = {}
    for t in tables:
        cols = [c[0] for c in con.execute(f"DESCRIBE {t}").fetchall()]
        rows = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        con.execute(f"COPY {t} TO '{PATHS.bi / (t + '.parquet')}' (FORMAT PARQUET)")
        formats = ["parquet"]
        if rows <= csv_row_limit:
            con.execute(f"COPY {t} TO '{PATHS.bi / (t + '.csv')}' (HEADER, DELIMITER ',')")
            formats.append("csv")
        manifest[t] = {"rows": int(rows), "columns": cols, "formats": formats}
    con.close()

    (PATHS.bi / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (PATHS.bi / "CONNECT.md").write_text(_GUIDE)
    log.info("exported %d tables to %s", len(tables), PATHS.bi)
    return {"tables": len(tables), "path": str(PATHS.bi)}
