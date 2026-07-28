"""Pytest fixtures for patient intake form tests."""

import pytest

# The env vars patient_intake.config resolves at import time come from
# [tool.pytest.ini_options] env in pyproject.toml, via pytest-env.


class _NoSecrets:
    """Stand-in for st.secrets that behaves like a missing secrets.toml."""

    def _fail(self, *args, **kwargs):
        raise FileNotFoundError("No secrets.toml in tests")

    __getitem__ = _fail
    __getattr__ = _fail
    __contains__ = _fail
    get = _fail


@pytest.fixture(autouse=True)
def no_secrets_file(monkeypatch):
    """Keep tests independent of a developer's local .streamlit/secrets.toml."""
    from patient_intake import config

    monkeypatch.setattr(config.st, "secrets", _NoSecrets())


@pytest.fixture
def email_env(monkeypatch):
    """Set a complete email env var configuration without SMTP_LOGIN."""
    monkeypatch.setenv("SMTP_SERVER", "email-smtp.us-east-1.amazonaws.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SENDER_EMAIL", "sender@example.com")
    monkeypatch.setenv("SENDER_PASSWORD", "secret")
    monkeypatch.setenv("RECIPIENT_EMAIL", "recipient@example.com")
    monkeypatch.delenv("SMTP_LOGIN", raising=False)
    return monkeypatch


@pytest.fixture
def no_email_env(monkeypatch):
    """Remove every email env var so the secrets fallback is used."""
    for name in (
        "SMTP_SERVER",
        "SMTP_PORT",
        "SENDER_EMAIL",
        "SENDER_PASSWORD",
        "RECIPIENT_EMAIL",
        "SMTP_LOGIN",
    ):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


@pytest.fixture
def sample_form_data():
    """Sample form data for testing."""
    return {
        "patient_name": "Fluffy",
        "patient_species": 1,
        "patient_breed": 1,
        "patient_sex": 1,
        "birthday_day": 15,
        "birthday_month": 6,
        "birthday_year": 2020,
        "patient_owner_firstname": "John",
        "patient_owner_lastname": "Doe",
        "patient_address": "123 Main St",
        "patient_email": "john@example.com",
        "patient_phone": "5551234567",
        "address": "123 Main St",
        "email": "john@example.com",
        "phone": "5551234567",
        "city": "Des Moines",
        "state": "IA",
        "zip": "50309",
        "company_id": 1,
    }


@pytest.fixture
def sample_extra_fields():
    """Sample extra fields for testing."""
    return {
        "sec_owner_firstname": "Jane",
        "sec_owner_lastname": "Doe",
        "work_no": "5559876543",
        "alt_no": "",
        "employer": "Acme Corp",
        "drive_lic": "IA12345",
        "owner_day": 1,
        "owner_month": 1,
        "owner_year": 1980,
        "prev_visit": "No",
        "color": "Brown",
        "breed_not_listed": "",
        "pet_prev_visit": "No",
        "doctor": "Dr. Smith",
        "clinic_name": "Main St Vet",
    }


@pytest.fixture
def sample_fixtures(
    sample_form_data, sample_extra_fields, sample_species_map, sample_breed_map, sample_sex_map
):
    """The form data arguments shared by the email and PDF entry points."""
    return (
        sample_form_data,
        sample_extra_fields,
        sample_species_map,
        sample_breed_map,
        sample_sex_map,
    )


@pytest.fixture
def sample_species_map():
    """Sample species mapping for testing."""
    return {"Canine": 1, "Feline": 2, "Equine": 3}


@pytest.fixture
def sample_breed_map():
    """Sample breed mapping for testing."""
    return {"Labrador": 1, "Siamese": 2, "Arabian": 3}


@pytest.fixture
def sample_sex_map():
    """Sample sex mapping for testing."""
    return {"Male": 1, "Female": 2, "Castrated male": 3, "Spayed female": 4}
