# NYC Taxi Demand Platform

An end-to-end data platform over the NYC TLC trip record dataset. It ingests raw
trip files, cleans and validates them, models a DuckDB **star schema**, runs
**ride-volume forecasting** and **trip anomaly detection**, and publishes
**BI-ready marts** for Tableau / Power BI.

Built to mirror how a small data/analytics-engineering team ships a dataset: a
config-driven, testable pipeline with explicit data-quality contracts and a
clean serving layer, not a notebook.

## Architecture

```
                 ┌─────────┐   ┌──────────┐   ┌───────────┐   ┌────────────┐
TLC parquet ───▶ │ ingest  │─▶ │ staging  │─▶ │ warehouse │─▶ │ BI exports │
NASA-style API   │ (bronze)│   │ (silver) │   │  (gold)   │   │ csv/parquet│
                 └─────────┘   └────┬─────┘   └─────┬─────┘   │  + duckdb  │
                                    │               │         └────────────┘
                              ┌─────▼─────┐   ┌─────▼──────┐
                              │ quality   │   │ analytics  │
                              │ (pandera) │   │ forecast + │
                              └───────────┘   │ anomaly    │
                                              └────────────┘
```

- **Bronze** `data/raw/`: raw TLC parquet (or synthetic), untouched.
- **Silver** `data/staged/trips.parquet`: one normalized, typed, filtered trip
  schema across yellow + green, with engineered calendar/derived columns.
- **Gold** `exports/warehouse.duckdb`: star schema (`dim_*`, `fact_trip`) plus
  analytics marts (`mart_*`).
- **Serving** `exports/bi/`: every table as CSV + Parquet, with a connection
  guide.

## Data model (star schema)

| table | grain | notes |
| --- | --- | --- |
| `fact_trip` | one trip | measures + FKs to all dims |
| `dim_date` | one day | calendar attributes, week start |
| `dim_time` | one hour | day-part, rush-hour flag |
| `dim_zone` | one TLC zone | borough + centroid lat/lng |
| `dim_fleet` | yellow / green | label + colour |
| `mart_zone_demand` | zone | pickups, revenue, centroids (map) |
| `mart_hourly_volume` | fleet×weekday×hour | avg rides/day (heatmap) |
| `mart_daily_volume` | fleet×day | rides, revenue (trend) |
| `mart_route_flows` | OD pair | top flows with both centroids |
| `mart_forecast` | fleet×hour | held-out actual vs forecast + interval |
| `mart_forecast_metrics` | fleet×model | MAE/RMSE/MAPE/sMAPE |
| `mart_trip_anomalies` | trip | flagged trips + reasons + score |

## Quickstart

```bash
uv venv .venv --python 3.12
uv pip install -e ".[dev,geo]"          # geo extra computes real zone centroids
source .venv/bin/activate

taxiflow run-all                        # full pipeline (live download)
taxiflow run-all --source synthetic     # fully offline
taxiflow info                           # print resolved config
```

Run any stage on its own: `taxiflow ingest|stage|quality|warehouse|forecast|anomaly|viz|export`.

Configuration lives in [`config/settings.yaml`](config/settings.yaml) (data
window, cleaning thresholds, forecast horizon, …) and can be overridden with
`TAXI_*` environment variables.

## Analytics

- **Forecasting**: hourly pickup volume per fleet. A gradient-boosted model on
  calendar + Fourier (daily & weekly) features is benchmarked against a
  seasonal-naive baseline with a rolling-origin backtest; metrics land in
  `mart_forecast_metrics` / `mart_forecast_backtest`.
- **Anomaly detection**: `IsolationForest` over trip economics + interpretable
  business rules (zero-distance, implausible speed, fare/distance mismatch, …).

## Data quality

`taxiflow quality` validates a sample against a pandera contract derived from the
cleaning config and computes full-table metrics (row counts, null rates, ranges,
duplicate groups, freshness). Reports are written to `reports/data_quality/`.

## Tests

```bash
pytest          # runs entirely on synthetic data, no network
ruff check src
```

## Layout

```
config/            settings.yaml
sql/marts/         mart SQL (one file per mart)
src/taxiflow/      ingest · staging · quality · warehouse · analytics · viz · bi
tests/             pytest (synthetic fixtures)
data/ exports/ reports/   generated artifacts (gitignored)
```
