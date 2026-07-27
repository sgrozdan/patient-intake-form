"""Tests for email sender module."""

import logging
import smtplib
from unittest.mock import MagicMock

from patient_intake import email_sender
from patient_intake.email_sender import format_email_body, label_from_id

# Kept because the tests patch smtplib.SMTP itself, and a mock specced against
# an already patched attribute accepts anything.
REAL_SMTP = smtplib.SMTP


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
    server = MagicMock(spec=REAL_SMTP)
    server.send_message.return_value = {}  # what smtplib returns when nothing is refused
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


def test_send_email_logs_where_it_sent(monkeypatch, email_env, sample_fixtures, caplog):
    """The server-side log has to answer 'which server, which login'."""
    email_env.setenv("SMTP_LOGIN", "AKIAIOSFODNN7EXAMPLE")

    with caplog.at_level(logging.INFO, logger="patient_intake"):
        _send(monkeypatch, sample_fixtures)

    log = caplog.text
    assert "email-smtp.us-east-1.amazonaws.com" in log
    assert "AKIA***" in log
    assert "SMTP_LOGIN env var" in log
    assert "accepted by" in log
    assert "AKIAIOSFODNN7EXAMPLE" not in log
    assert "secret" not in log


def test_send_email_logs_the_failure_and_hides_it_from_the_form(
    monkeypatch, email_env, sample_fixtures, caplog
):
    """The patient gets a generic message, the operator gets the traceback."""
    errors = []
    monkeypatch.setattr(email_sender.st, "error", errors.append)
    monkeypatch.setattr(
        email_sender.smtplib,
        "SMTP",
        MagicMock(side_effect=smtplib.SMTPAuthenticationError(535, b"Credentials Invalid")),
    )

    with caplog.at_level(logging.INFO, logger="patient_intake"):
        sent = email_sender.send_email_with_pdf(
            b"%PDF-1.4", "intake.pdf", "Fluffy", *sample_fixtures
        )

    assert sent is False
    assert "Credentials Invalid" in caplog.text
    assert "Traceback" in caplog.text
    assert errors == ["Email delivery failed - the form was saved, please notify the clinic."]
    assert "Credentials Invalid" not in errors[0]


def test_send_email_logs_refused_recipients(monkeypatch, email_env, sample_fixtures, caplog):
    """A message the server takes but strips recipients from is not a success."""
    server = MagicMock(spec=REAL_SMTP)
    server.send_message.return_value = {"recipient@example.com": (550, b"User unknown")}
    smtp = MagicMock()
    smtp.return_value.__enter__.return_value = server
    monkeypatch.setattr(email_sender.smtplib, "SMTP", smtp)

    with caplog.at_level(logging.INFO, logger="patient_intake"):
        email_sender.send_email_with_pdf(b"%PDF-1.4", "intake.pdf", "Fluffy", *sample_fixtures)

    assert "refused recipients" in caplog.text
    assert "User unknown" in caplog.text


def test_smtp_debug_is_off_unless_requested(monkeypatch, email_env, sample_fixtures):
    """The protocol trace carries the credentials, so it must be opt-in."""
    _, _, server = _send(monkeypatch, sample_fixtures)
    server.set_debuglevel.assert_called_once_with(0)

    email_env.setenv("SMTP_DEBUG", "1")
    _, _, server = _send(monkeypatch, sample_fixtures)
    server.set_debuglevel.assert_called_once_with(1)
