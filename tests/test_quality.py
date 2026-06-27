import duckdb
import pytest
from pandera.errors import SchemaError, SchemaErrors

from taxiflow.quality.schemas import trips_schema
from taxiflow.staging.clean import _build_query, _fleet_select


def _staged(raw, settings, tmp_path):
    path = tmp_path / "r.parquet"
    raw.to_parquet(path, index=False)
    sel = _fleet_select("yellow", str(path), None)
    return duckdb.connect().execute(_build_query([sel], settings)).df()


def test_contract_passes_on_clean(tmp_path, raw_yellow, settings):
    df = _staged(raw_yellow, settings, tmp_path)
    trips_schema(settings).validate(df)


def test_contract_fails_on_corrupted(tmp_path, raw_yellow, settings):
    df = _staged(raw_yellow, settings, tmp_path)
    df.loc[: len(df) // 2, "fare_amount"] = 10_000.0
    with pytest.raises((SchemaError, SchemaErrors)):
        trips_schema(settings).validate(df)
