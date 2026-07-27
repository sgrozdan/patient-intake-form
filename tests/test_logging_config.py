"""Tests for application logging setup."""

import logging
import sys

import pytest

from patient_intake import logging_config


@pytest.fixture
def clean_logger():
    """Restore the package logger after tests that configure it for real."""
    logger = logging.getLogger(logging_config.LOGGER_NAME)
    handlers, level, propagate = logger.handlers[:], logger.level, logger.propagate
    logger.handlers = []
    yield logger
    logger.handlers, logger.level, logger.propagate = handlers, level, propagate


def test_configure_logging_writes_to_stdout(clean_logger, monkeypatch):
    """Docker collects stdout, so that is where the records have to go."""
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    logging_config.configure_logging()

    assert len(clean_logger.handlers) == 1
    assert clean_logger.handlers[0].stream is sys.stdout
    assert clean_logger.level == logging.INFO
    assert clean_logger.propagate is False


def test_configure_logging_is_idempotent(clean_logger):
    """Streamlit reruns the script on every interaction."""
    logging_config.configure_logging()
    logging_config.configure_logging()

    assert len(clean_logger.handlers) == 1


def test_configure_logging_honours_log_level(clean_logger, monkeypatch):
    """LOG_LEVEL selects the verbosity."""
    monkeypatch.setenv("LOG_LEVEL", "debug")

    logging_config.configure_logging()

    assert clean_logger.level == logging.DEBUG


def test_configure_logging_ignores_unknown_log_level(clean_logger, monkeypatch):
    """An unusable LOG_LEVEL must not take the application down."""
    monkeypatch.setenv("LOG_LEVEL", "chatty")

    logging_config.configure_logging()

    assert clean_logger.level == logging.INFO


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("AKIAIOSFODNN7EXAMPLE", "AKIA***"),
        ("short", "***"),
        ("", "<empty>"),
    ],
)
def test_mask_keeps_credentials_recognisable_but_unusable(value, expected):
    """Enough to tell which login is in use, not enough to reuse it."""
    assert logging_config.mask(value) == expected
