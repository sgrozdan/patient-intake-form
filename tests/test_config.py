"""Tests for email configuration resolution."""

import pytest

from patient_intake import config

SECRETS_EMAIL = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "sender@example.com",
    "sender_password": "secret",
    "recipient_email": "recipient@example.com",
}


def test_env_smtp_login_defaults_to_sender_email(email_env):
    """Without SMTP_LOGIN the sender address is used as the login."""
    cfg = config.get_email_config()

    assert cfg["smtp_login"] == "sender@example.com"
    assert cfg["sender_email"] == "sender@example.com"
    assert cfg["smtp_port"] == 587


def test_env_smtp_login_is_independent_from_sender_email(email_env):
    """SMTP_LOGIN overrides the login without touching the sender address."""
    email_env.setenv("SMTP_LOGIN", "AKIAIOSFODNN7EXAMPLE")

    cfg = config.get_email_config()

    assert cfg["smtp_login"] == "AKIAIOSFODNN7EXAMPLE"
    assert cfg["sender_email"] == "sender@example.com"


def test_env_empty_smtp_login_falls_back_to_sender_email(email_env):
    """An empty SMTP_LOGIN (e.g. an unset docker-compose variable) is ignored."""
    email_env.setenv("SMTP_LOGIN", "")

    assert config.get_email_config()["smtp_login"] == "sender@example.com"


def test_secrets_smtp_login_defaults_to_sender_email(no_email_env):
    """Secrets without smtp_login keep the previous behaviour."""
    no_email_env.setattr(config.st, "secrets", {"email": SECRETS_EMAIL})

    assert config.get_email_config()["smtp_login"] == "sender@example.com"


def test_secrets_smtp_login_is_independent_from_sender_email(no_email_env):
    """smtp_login in secrets.toml overrides the login."""
    secrets = {"email": {**SECRETS_EMAIL, "smtp_login": "AKIAIOSFODNN7EXAMPLE"}}
    no_email_env.setattr(config.st, "secrets", secrets)

    cfg = config.get_email_config()

    assert cfg["smtp_login"] == "AKIAIOSFODNN7EXAMPLE"
    assert cfg["sender_email"] == "sender@example.com"


def test_env_smtp_login_overrides_secrets(no_email_env):
    """SMTP_LOGIN applies even when the rest of the config comes from secrets."""
    secrets = {"email": {**SECRETS_EMAIL, "smtp_login": "from-secrets"}}
    no_email_env.setattr(config.st, "secrets", secrets)
    no_email_env.setenv("SMTP_LOGIN", "AKIAIOSFODNN7EXAMPLE")

    assert config.get_email_config()["smtp_login"] == "AKIAIOSFODNN7EXAMPLE"


def test_partial_env_falls_back_to_secrets_but_keeps_smtp_login(no_email_env):
    """An incomplete env config must not silently drop SMTP_LOGIN."""
    no_email_env.setattr(config.st, "secrets", {"email": SECRETS_EMAIL})
    no_email_env.setenv("SMTP_SERVER", "email-smtp.us-east-1.amazonaws.com")
    no_email_env.setenv("SMTP_LOGIN", "AKIAIOSFODNN7EXAMPLE")

    cfg = config.get_email_config()

    assert cfg["smtp_login"] == "AKIAIOSFODNN7EXAMPLE"
    assert cfg["smtp_server"] == "smtp.gmail.com"


def test_secrets_smtp_port_is_coerced_to_int(no_email_env):
    """A quoted port in secrets.toml must not reach smtplib as a string."""
    no_email_env.setattr(config.st, "secrets", {"email": {**SECRETS_EMAIL, "smtp_port": "587"}})

    assert config.get_email_config()["smtp_port"] == 587


def test_missing_secrets_file_raises(no_email_env):
    """No env vars and no secrets.toml is a configuration error."""
    with pytest.raises(ValueError, match="Missing email config"):
        config.get_email_config()


def test_missing_email_section_raises(no_email_env):
    """A secrets.toml without an email section is a configuration error."""
    no_email_env.setattr(config.st, "secrets", {})

    with pytest.raises(ValueError, match="Missing email config"):
        config.get_email_config()


def test_incomplete_secrets_section_raises(no_email_env):
    """Missing keys are reported instead of authenticating with None."""
    secrets = {"email": {k: v for k, v in SECRETS_EMAIL.items() if k != "sender_email"}}
    no_email_env.setattr(config.st, "secrets", secrets)

    with pytest.raises(ValueError, match="missing sender_email"):
        config.get_email_config()
