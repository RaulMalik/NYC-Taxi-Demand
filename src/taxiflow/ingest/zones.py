"""Build the taxi-zone reference table (id, name, borough, centroid lat/lng)."""
from __future__ import annotations

import logging

import pandas as pd

from ..config import PATHS, Settings
from .tlc import download

log = logging.getLogger("taxiflow.ingest")

DIM_ZONE_PATH = PATHS.reference / "dim_zone.parquet"
_CENTROID_CACHE = PATHS.reference / "zone_centroids.parquet"

BOROUGH_CENTROID = {
    "Manhattan": (40.7831, -73.9712),
    "Brooklyn": (40.6782, -73.9442),
    "Queens": (40.7282, -73.7949),
    "Bronx": (40.8448, -73.8648),
    "Staten Island": (40.5795, -74.1502),
    "EWR": (40.6895, -74.1745),
}
_NYC = (40.7128, -74.0060)


def _zone_lookup(settings: Settings) -> pd.DataFrame:
    dest = PATHS.reference / "taxi_zone_lookup.csv"
    try:
        download(settings.ingest.zone_lookup_url, dest)
        df = pd.read_csv(dest)
    except Exception as exc:  # offline: synthesise a complete 1..263 lookup
        log.warning("zone lookup unavailable (%s); generating placeholder zones", exc)
        boroughs = list(BOROUGH_CENTROID)
        df = pd.DataFrame(
            {
                "LocationID": range(1, 264),
                "Borough": [boroughs[i % len(boroughs)] for i in range(263)],
                "Zone": [f"Zone {i}" for i in range(1, 264)],
                "service_zone": "Boro Zone",
            }
        )
    return df.rename(columns={"LocationID": "location_id", "Borough": "borough",
                              "Zone": "zone", "service_zone": "service_zone"})


def _centroids_from_shapefile(settings: Settings) -> pd.DataFrame | None:
    try:
        import geopandas as gpd
    except ImportError:
        return None
    try:
        import zipfile

        zip_path = PATHS.reference / "taxi_zones.zip"
        download(settings.ingest.zone_shapefile_url, zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            shp = next(n for n in zf.namelist() if n.endswith(".shp"))
        gdf = gpd.read_file(f"zip://{zip_path}!{shp}")
        cen = gdf.geometry.centroid.to_crs(4326)  # centroid in projected CRS, then to lat/lng
        out = pd.DataFrame(
            {"location_id": gdf["LocationID"].astype(int), "lat": cen.y, "lng": cen.x}
        )
        out.to_parquet(_CENTROID_CACHE, index=False)
        log.info("computed %d zone centroids from shapefile", len(out))
        return out
    except Exception as exc:
        log.warning("centroid computation failed (%s); using borough fallback", exc)
        return None


def build_zone_dim(settings: Settings) -> pd.DataFrame:
    PATHS.reference.mkdir(parents=True, exist_ok=True)
    zones = _zone_lookup(settings)

    centroids = None
    if _CENTROID_CACHE.exists():
        centroids = pd.read_parquet(_CENTROID_CACHE)
    if centroids is None:
        centroids = _centroids_from_shapefile(settings)

    if centroids is not None:
        zones = zones.merge(centroids, on="location_id", how="left")
    else:
        zones["lat"] = pd.NA
        zones["lng"] = pd.NA

    fallback = zones["borough"].map(BOROUGH_CENTROID)
    zones["lat"] = zones["lat"].fillna(fallback.map(lambda v: v[0] if isinstance(v, tuple) else _NYC[0]))
    zones["lng"] = zones["lng"].fillna(fallback.map(lambda v: v[1] if isinstance(v, tuple) else _NYC[1]))

    zones = zones[["location_id", "zone", "borough", "service_zone", "lat", "lng"]]
    zones.to_parquet(DIM_ZONE_PATH, index=False)
    log.info("zone reference -> %s (%d zones)", DIM_ZONE_PATH.name, len(zones))
    return zones
