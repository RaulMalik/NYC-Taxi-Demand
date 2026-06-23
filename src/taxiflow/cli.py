"""taxiflow command line: run the whole pipeline or any single stage."""
from __future__ import annotations

import typer

from .analytics import run_anomaly, run_forecast
from .bi import run_export
from .config import get_settings
from .ingest import run_ingest
from .logging_setup import setup_logging
from .pipeline import run_all
from .quality import run_quality
from .staging import run_staging
from .viz import render_all
from .warehouse import run_warehouse

app = typer.Typer(add_completion=False, help="NYC taxi demand data platform.")


def _settings(config: str | None, source: str | None):
    setup_logging()
    s = get_settings(config)
    if source:
        s.ingest.source = source
    return s


Config = typer.Option(None, "--config", "-c", help="Path to settings.yaml")
Source = typer.Option(None, "--source", help="Override ingest source: live | synthetic")


@app.command()
def ingest(config: str | None = Config, source: str | None = Source):
    run_ingest(_settings(config, source))


@app.command()
def stage(config: str | None = Config):
    run_staging(_settings(config, None))


@app.command()
def quality(config: str | None = Config):
    run_quality(_settings(config, None))


@app.command()
def warehouse(config: str | None = Config):
    run_warehouse(_settings(config, None))


@app.command()
def forecast(config: str | None = Config):
    run_forecast(_settings(config, None))


@app.command()
def anomaly(config: str | None = Config):
    run_anomaly(_settings(config, None))


@app.command()
def viz(config: str | None = Config):
    render_all(_settings(config, None))


@app.command()
def export(config: str | None = Config):
    run_export(_settings(config, None))


@app.command(name="run-all")
def run_all_cmd(config: str | None = Config, source: str | None = Source):
    run_all(_settings(config, source))


@app.command()
def info(config: str | None = Config):
    s = _settings(config, None)
    typer.echo(s.model_dump_json(indent=2))


def main():
    app()


if __name__ == "__main__":
    main()
