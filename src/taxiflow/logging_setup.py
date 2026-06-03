import logging

from rich.logging import RichHandler

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    global _CONFIGURED
    if not _CONFIGURED:
        logging.basicConfig(
            level=level,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(rich_tracebacks=True, show_path=False, markup=True)],
        )
        _CONFIGURED = True
    return logging.getLogger("taxiflow")
