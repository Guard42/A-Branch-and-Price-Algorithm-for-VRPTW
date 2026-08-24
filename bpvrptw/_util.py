"""Shared utilities for the bpvrptw package."""

from __future__ import annotations

import logging

LOGGER_ROOT = "bpvrptw"


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the ``bpvrptw`` hierarchy.

    Args:
        name: Usually ``__name__`` of the calling module.

    Returns:
        A child of the ``bpvrptw`` root logger.
    """
    if name == LOGGER_ROOT or name.startswith(LOGGER_ROOT + "."):
        return logging.getLogger(name)
    return logging.getLogger(f"{LOGGER_ROOT}.{name}")


def setup_logging(level: int = logging.INFO) -> None:
    """Attach a stream handler to the :data:`LOGGER_ROOT` logger.

    The library never configures logging as an import side effect; call this
    helper explicitly (the CLI does) to see log output.

    Args:
        level: Logging level for the ``bpvrptw`` logger, e.g. ``logging.DEBUG``.
    """
    logger = logging.getLogger(LOGGER_ROOT)
    if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(level)
