"""Tests for validation and the submission path of the form."""

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from patient_intake import app

VALID_FIELDS = {
    "owner_name": "John Doe",
    "email": "john@example.com",
    "cell_no": "5551234567",
    "owner_address": "123 Main St",
    "city": "Des Moines",
    "state": "IA",
    "zip_code": "50309",
    "pet_name": "Fluffy",
    "breed": "Labrador",
    "breed_non_listed": "",
    "patient_sex": "Male",
    "patient_species": "Canine",
    "agree": True,
}

# What _handle_submit needs on top of the validated fields.
EXTRA_FIELDS = {
    "sec_owner_name": "",
    "work_no": "",
    "alt_no": "",
    "employer": "",
    "drive_lic": "",
    "owner_day": 1,
    "owner_month": 1,
    "owner_year": 1980,
    "prev_visit": "No",
    "color": "Brown",
    "day": 15,
    "month": 6,
    "year": 2020,
    "pet_prev_visit": "No",
    "doctor": "Dr. Smith",
    "clinic_name": "Main St Vet",
}


@pytest.fixture
def maps(sample_species_map, sample_breed_map, sample_sex_map):
    """The reference data both _validate and _handle_submit take."""
    return {
        "species_map": sample_species_map,
        "breed_map": sample_breed_map,
        "sex_map": sample_sex_map,
    }


@pytest.fixture
def quiet_streamlit(monkeypatch):
    """Collect what the form would render instead of rendering it."""
    shown = {"warning": [], "error": [], "success": []}
    for name in shown:
        monkeypatch.setattr(app.st, name, shown[name].append)
    monkeypatch.setattr(app.st, "write", lambda *a, **k: None)
    monkeypatch.setattr(app.st, "balloons", lambda: None)
    return shown


def validate(maps, **overrides):
    """Validate an otherwise valid submission with the given fields overridden."""
    return app._validate(**{**VALID_FIELDS, **overrides}, **maps)


def test_valid_submission_has_no_field_errors(maps):
    """The happy path must not flag anything."""
    assert validate(maps) == {}


@pytest.mark.parametrize(
    ("field", "value", "flagged"),
    [
        ("zip_code", "", "zip_code"),
        ("zip_code", "5030", "zip_code"),
        ("owner_name", "", "owner_name"),
        ("owner_name", "John", "owner_name"),
        ("email", "", "email"),
        ("email", "john@example", "email"),
        ("cell_no", "555", "cell_no"),
        ("owner_address", "", "owner_address"),
        ("city", "", "city"),
        ("state", "Iowa", "state"),
        ("pet_name", "Fluffy2", "pet_name"),
        ("agree", False, "agree"),
        ("patient_species", "Unlisted species", "species"),
        ("patient_sex", "Unlisted sex", "sex"),
    ],
)
def test_invalid_fields_are_flagged_with_a_message(maps, field, value, flagged):
    """Every rejection names its field, so nothing is refused silently."""
    errors = validate(maps, **{field: value})

    assert flagged in errors
    assert errors[flagged].strip()


def test_unlisted_breed_is_accepted_when_typed_in(maps):
    """The free-text breed is the way out when the list has no match."""
    assert validate(maps, breed="Not in list", breed_non_listed="Tamaskan") == {}
    assert "breed" in validate(maps, breed="Not in list", breed_non_listed="")


def test_submit_sends_the_email_and_logs_the_patient(maps, quiet_streamlit, monkeypatch, caplog):
    """A validated submission reaches the API, the PDF and the email."""
    api = MagicMock()
    api.return_value.status_code = 200
    api.return_value.json.return_value = {"result": "success", "patient_id": 42}
    monkeypatch.setattr(app, "submit_patient", api)
    monkeypatch.setattr(app, "fill_pdf_with_fitz", MagicMock())
    monkeypatch.setattr(app, "send_email_with_pdf", MagicMock(return_value=True))

    fields = {k: v for k, v in VALID_FIELDS.items() if k != "agree"}
    with caplog.at_level(logging.INFO, logger="patient_intake"):
        app._handle_submit(**fields, **EXTRA_FIELDS, **maps)

    api.assert_called_once()
    app.send_email_with_pdf.assert_called_once()
    assert "Patient created: id=42, email sent=True" in caplog.text
    assert quiet_streamlit["warning"] == []


def test_inputs_are_collected_by_a_form():
    """Loose text inputs only reach the server on blur, which breaks autofill."""
    source = Path(app.__file__).read_text()

    assert 'with st.form("intake_form"):' in source
    assert 'st.form_submit_button("Submit")' in source
    assert 'st.button("Submit")' not in source
