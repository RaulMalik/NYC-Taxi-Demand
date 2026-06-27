import duckdb
import pandas as pd

from taxiflow.config import PATHS


def _seed(con):
    dim_zone = pd.DataFrame(
        {
            "location_id": [1, 2, 3],
            "zone": ["A", "B", "C"],
            "borough": ["Manhattan", "Brooklyn", "Queens"],
            "service_zone": ["x", "x", "x"],
            "lat": [40.75, 40.68, 40.73],
            "lng": [-73.98, -73.94, -73.79],
        }
    )
    dim_date = pd.DataFrame(
        {
            "date_key": [20220103, 20220104],
            "date": pd.to_datetime(["2022-01-03", "2022-01-04"]),
            "weekday": [0, 1],
            "weekday_name": ["Monday", "Tuesday"],
            "is_weekend": [False, False],
        }
    )
    rows = []
    for _ in range(6):
        rows.append((1, 2, "yellow", 8, 20220103))
    for _ in range(5):
        rows.append((2, 3, "green", 18, 20220104))
    fact = pd.DataFrame(rows, columns=["pickup_location_id", "dropoff_location_id",
                                       "fleet", "pickup_hour", "date_key"])
    fact["trip_id"] = range(len(fact))
    fact["trip_distance"] = 2.0
    fact["fare_amount"] = 12.0
    fact["tip_amount"] = 2.0
    fact["total_amount"] = 15.0
    fact["trip_duration_min"] = 10.0
    fact["avg_speed_mph"] = 12.0

    con.register("dz", dim_zone)
    con.register("dd", dim_date)
    con.register("ft", fact)
    con.execute("CREATE TABLE dim_zone AS SELECT * FROM dz")
    con.execute("CREATE TABLE dim_date AS SELECT * FROM dd")
    con.execute("CREATE TABLE fact_trip AS SELECT * FROM ft")


def test_marts_build_and_aggregate():
    con = duckdb.connect()
    _seed(con)
    for path in sorted((PATHS.sql / "marts").glob("*.sql")):
        con.execute(path.read_text())

    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    assert {"mart_zone_demand", "mart_hourly_volume", "mart_daily_volume",
            "mart_route_flows"} <= tables

    zd = con.execute("SELECT pickups FROM mart_zone_demand WHERE location_id = 1").fetchone()[0]
    assert zd == 6

    flow = con.execute(
        "SELECT trips FROM mart_route_flows WHERE pickup_location_id = 1 AND dropoff_location_id = 2"
    ).fetchone()[0]
    assert flow == 6

    daily = con.execute("SELECT sum(rides) FROM mart_daily_volume").fetchone()[0]
    assert daily == 11
