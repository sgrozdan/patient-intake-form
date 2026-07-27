"""Tests for email sender module."""

import smtplib
from unittest.mock import MagicMock

from patient_intake import email_sender
from patient_intake.email_sender import format_email_body, label_from_id


def test_label_from_id_found():
    """Test label lookup when ID exists."""
    mapping = {"Dog": 1, "Cat": 2}
    assert label_from_id(mapping, 1) == "Dog"
    assert label_from_id(mapping, 2) == "Cat"


def test_label_from_id_not_found():
    """Test label lookup when ID doesn't exist."""
    mapping = {"Dog": 1}
    assert label_from_id(mapping, 99) == ""
    assert label_from_id(mapping, 99, "Unknown") == "Unknown"


def test_format_email_body(
    sample_form_data, sample_extra_fields, sample_species_map, sample_breed_map, sample_sex_map
):
    """Test email body formatting."""
    body = format_email_body(
        sample_form_data,
        sample_extra_fields,
        sample_species_map,
        sample_breed_map,
        sample_sex_map,
    )

    assert "John Doe" in body
    assert "Fluffy" in body
    assert "Canine" in body
    assert "Dr. Smith" in body
    assert "Main St Vet" in body


def _send(monkeypatch, sample_fixtures):
    """Send a form over a mocked SMTP connection; returns (result, SMTP, server)."""
    server = MagicMock(spec=smtplib.SMTP)
    smtp = MagicMock()
    smtp.return_value.__enter__.return_value = server
    monkeypatch.setattr(email_sender.smtplib, "SMTP", smtp)

    sent = email_sender.send_email_with_pdf(b"%PDF-1.4", "intake.pdf", "Fluffy", *sample_fixtures)
    return sent, smtp, server


def test_send_email_authenticates_with_smtp_login(monkeypatch, email_env, sample_fixtures):
    """The SMTP login is used for auth while From stays the sender address."""
    email_env.setenv("SMTP_LOGIN", "AKIAIOSFODNN7EXAMPLE")

    sent, smtp, server = _send(monkeypatch, sample_fixtures)

    assert sent is True
    smtp.assert_called_once_with(
        "email-smtp.us-east-1.amazonaws.com", 587, timeout=email_sender.SMTP_TIMEOUT
    )
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("AKIAIOSFODNN7EXAMPLE", "secret")
    msg = server.send_message.call_args[0][0]
    assert msg["From"] == "sender@example.com"
    assert msg["To"] == "recipient@example.com"


def test_send_email_without_smtp_login_uses_sender_email(monkeypatch, email_env, sample_fixtures):
    """Providers like Gmail keep authenticating with the sender address."""
    sent, _, server = _send(monkeypatch, sample_fixtures)

    assert sent is True
    server.login.assert_called_once_with("sender@example.com", "secret")


def test_send_email_reports_misconfiguration_as_failed_email(
    monkeypatch, no_email_env, sample_fixtures
):
    """A broken email config must not surface as a failed form submission."""
    sent, smtp, _ = _send(monkeypatch, sample_fixtures)

    assert sent is False
    smtp.assert_not_called()
