"""Download raw NYC TLC trip parquet files."""
from __future__ import annotations

import logging
from pathlib import Path

import requests

from ..config import PATHS, Settings

log = logging.getLogger("taxiflow.ingest")


def raw_path(fleet: str, month: str) -> Path:
    return PATHS.raw / f"{fleet}_tripdata_{month}.parquet"


def download(url: str, dest: Path, force: bool = False, timeout: int = 120) -> Path:
    if dest.exists() and not force:
        log.info("cached %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    log.info("downloading %s", url)
    with requests.get(url, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
        tmp.replace(dest)
    log.info("saved %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
    return dest


def ingest_live(settings: Settings) -> list[dict]:
    cfg = settings.ingest
    manifest = []
    for fleet in cfg.fleets:
        for month in cfg.months:
            url = f"{cfg.tlc_base_url}/{fleet}_tripdata_{month}.parquet"
            dest = download(url, raw_path(fleet, month))
            manifest.append({"fleet": fleet, "month": month, "path": str(dest), "source": "live"})
    return manifest
