import pandas as pd
import pytest

from taxiflow.config import Settings
from taxiflow.ingest.synthetic import generate_fleet_month


@pytest.fixture
def settings():
    return Settings()


@pytest.fixture
def raw_yellow():
    return generate_fleet_month("yellow", "2022-01", n=5000, seed=1)


@pytest.fixture
def raw_green():
    return generate_fleet_month("green", "2022-01", n=2000, seed=2)


@pytest.fixture
def hourly_series():
    idx = pd.date_range("2022-01-01", periods=24 * 30, freq="h")
    base = 200 + 120 * (idx.hour.isin([8, 9, 17, 18, 19]).astype(float))
    base = base * (0.7 + 0.3 * (idx.dayofweek < 5).astype(float))
    return pd.DataFrame({"ds": idx, "y": base + (idx.hour * 3)})
