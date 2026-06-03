"""Typed, file-driven configuration for the taxi platform."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "settings.yaml"


class IngestConfig(BaseModel):
    source: str = "live"
    fleets: list[str] = Field(default_factory=lambda: ["yellow", "green"])
    months: list[str] = Field(default_factory=lambda: ["2022-01", "2022-02"])
    tlc_base_url: str = "https://d37ci6vzurychx.cloudfront.net/trip-data"
    zone_lookup_url: str = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
    zone_shapefile_url: str = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip"
    sample_rows: int | None = None


class WindowConfig(BaseModel):
    start: str = "2022-01-01"
    end: str = "2022-03-01"


class CleaningConfig(BaseModel):
    min_fare: float = 0.0
    max_fare: float = 500.0
    min_distance: float = 0.0
    max_distance: float = 100.0
    min_duration_min: float = 1.0
    max_duration_min: float = 180.0
    max_passengers: int = 6


class ForecastConfig(BaseModel):
    freq: str = "h"
    test_days: int = 7
    fleets: list[str] = Field(default_factory=lambda: ["yellow"])


class AnomalyConfig(BaseModel):
    contamination: float = 0.01
    sample_rows: int = 200_000


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TAXI_", env_nested_delimiter="__", extra="ignore")

    project_name: str = "nyc-taxi-demand-platform"
    ingest: IngestConfig = Field(default_factory=IngestConfig)
    window: WindowConfig = Field(default_factory=WindowConfig)
    cleaning: CleaningConfig = Field(default_factory=CleaningConfig)
    forecast: ForecastConfig = Field(default_factory=ForecastConfig)
    anomaly: AnomalyConfig = Field(default_factory=AnomalyConfig)


class Paths:
    def __init__(self, root: Path = ROOT):
        self.root = root
        self.data = root / "data"
        self.raw = self.data / "raw"
        self.staged = self.data / "staged"
        self.marts = self.data / "marts"
        self.reference = self.data / "reference"
        self.exports = root / "exports"
        self.bi = self.exports / "bi"
        self.figures = self.exports / "figures"
        self.reports = root / "reports"
        self.quality = self.reports / "data_quality"
        self.warehouse = self.exports / "warehouse.duckdb"
        self.sql = root / "sql"

    def ensure(self) -> Paths:
        for p in (self.raw, self.staged, self.marts, self.reference,
                  self.bi, self.figures, self.quality):
            p.mkdir(parents=True, exist_ok=True)
        return self


PATHS = Paths()


def _load_yaml(path: Path) -> dict:
    if path.exists():
        with open(path) as fh:
            return yaml.safe_load(fh) or {}
    return {}


@lru_cache(maxsize=8)
def get_settings(config_path: str | None = None) -> Settings:
    path = Path(config_path) if config_path else DEFAULT_CONFIG
    return Settings(**_load_yaml(path))
