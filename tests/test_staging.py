import duckdb

from taxiflow.staging.clean import _build_query, _fleet_select


def test_cleaning_filters_and_features(tmp_path, raw_yellow, settings):
    path = tmp_path / "yellow.parquet"
    raw_yellow.to_parquet(path, index=False)

    sel = _fleet_select("yellow", str(path), None)
    df = duckdb.connect().execute(_build_query([sel], settings)).df()

    c = settings.cleaning
    assert df["fare_amount"].between(c.min_fare, c.max_fare).all()
    assert df["trip_distance"].between(c.min_distance, c.max_distance).all()
    assert df["trip_duration_min"].between(c.min_duration_min, c.max_duration_min).all()
    assert (df["dropoff_datetime"] > df["pickup_datetime"]).all()
    assert df["pickup_hour"].between(0, 23).all()
    assert df["pickup_weekday"].between(0, 6).all()
    assert "avg_speed_mph" in df.columns


def test_negative_fares_removed(tmp_path, raw_yellow, settings):
    raw_yellow.loc[:9, "fare_amount"] = -10.0
    path = tmp_path / "yellow.parquet"
    raw_yellow.to_parquet(path, index=False)
    sel = _fleet_select("yellow", str(path), None)
    df = duckdb.connect().execute(_build_query([sel], settings)).df()
    assert (df["fare_amount"] >= 0).all()
