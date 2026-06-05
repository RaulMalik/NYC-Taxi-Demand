import json
import logging

from ..config import PATHS, Settings
from .synthetic import ingest_synthetic
from .tlc import ingest_live
from .zones import build_zone_dim

log = logging.getLogger("taxiflow.ingest")


def run_ingest(settings: Settings) -> dict:
    PATHS.ensure()
    if settings.ingest.source == "synthetic":
        manifest = ingest_synthetic(settings)
    else:
        try:
            manifest = ingest_live(settings)
        except Exception as exc:
            log.warning("live ingest failed (%s); falling back to synthetic", exc)
            manifest = ingest_synthetic(settings)

    build_zone_dim(settings)
    out = {"source": settings.ingest.source, "files": manifest}
    (PATHS.raw / "manifest.json").write_text(json.dumps(out, indent=2))
    return out
