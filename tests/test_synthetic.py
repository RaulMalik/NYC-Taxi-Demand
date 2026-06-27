from taxiflow.ingest.synthetic import generate_fleet_month


def test_schema_and_prefix(raw_yellow, raw_green):
    assert "tpep_pickup_datetime" in raw_yellow.columns
    assert "lpep_pickup_datetime" in raw_green.columns
    for col in ("PULocationID", "DOLocationID", "fare_amount", "trip_distance"):
        assert col in raw_yellow.columns


def test_deterministic():
    a = generate_fleet_month("yellow", "2022-01", n=1000, seed=42)
    b = generate_fleet_month("yellow", "2022-01", n=1000, seed=42)
    assert a.equals(b)


def test_zone_ids_in_range(raw_yellow):
    assert raw_yellow["PULocationID"].between(1, 263).all()
    assert raw_yellow["DOLocationID"].between(1, 263).all()
