"""Application logging setup.

Streamlit configures logging for its own loggers only, so without this the
application's log records are dropped instead of reaching the container output.
"""

import logging
import os
import sys

LOGGER_NAME = "patient_intake"
DEFAULT_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def _level_from_env() -> int:
    """Read LOG_LEVEL, falling back to the default for unknown values."""
    level = getattr(logging, os.environ.get("LOG_LEVEL", DEFAULT_LEVEL).upper(), None)
    return level if isinstance(level, int) else getattr(logging, DEFAULT_LEVEL)


def configure_logging() -> None:
    """Send the application's logs to stdout, where Docker collects them.

    Safe to call repeatedly: Streamlit reruns the script on every interaction.
    """
    from patient_intake import __version__

    logger = logging.getLogger(LOGGER_NAME)
    level = _level_from_env()
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
        # Our own handler already writes to stdout; propagating would duplicate
        # every record through Streamlit's root handler.
        logger.propagate = False
        # Printed once per process: tells from the container output alone which
        # version is running and whether these logs can be trusted to be complete.
        logger.info(
            "patient-intake %s started, logging at %s", __version__, logging.getLevelName(level)
        )


def get_logger(name: str) -> logging.Logger:
    """Return a logger inside the application's namespace.

    Do not build the name from __name__ in the entry point: Streamlit executes
    app.py as __main__, so the records would land outside the namespace
    configure_logging() sets up and be dropped.
    """
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def mask(value: str) -> str:
    """Shorten a credential for logging: enough to recognise, not to reuse."""
    if not value:
        return "<empty>"
    return value[:4] + "***" if len(value) > 8 else "***"
