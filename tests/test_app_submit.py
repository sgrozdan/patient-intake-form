"""Tests for the submission path of the form."""

import logging
from unittest.mock import MagicMock

import pytest

from patient_intake import app

VALID_SUBMISSION = {
    "owner_name": "John Doe",
    "sec_owner_name": "",
    "email": "john@example.com",
    "cell_no": "5551234567",
    "work_no": "",
    "alt_no": "",
    "employer": "",
    "drive_lic": "",
    "owner_address": "123 Main St",
    "city": "Des Moines",
    "state": "IA",
    "zip_code": "50309",
    "owner_day": 1,
    "owner_month": 1,
    "owner_year": 1980,
    "prev_visit": "No",
    "pet_name": "Fluffy",
    "breed": "Labrador",
    "breed_non_listed": "",
    "color": "Brown",
    "day": 15,
    "month": 6,
    "year": 2020,
    "patient_sex": "Male",
    "patient_species": "Canine",
    "pet_prev_visit": "No",
    "doctor": "Dr. Smith",
    "clinic_name": "Main St Vet",
    "agree": True,
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


@pytest.fixture
def submit(monkeypatch, sample_species_map, sample_breed_map, sample_sex_map):
    """Call the submit handler with a valid submission, overridden per test."""
    api = MagicMock()
    api.return_value.status_code = 200
    api.return_value.json.return_value = {"result": "success", "patient_id": 42}
    monkeypatch.setattr(app, "submit_patient", api)
    monkeypatch.setattr(app, "fill_pdf_with_fitz", MagicMock())
    monkeypatch.setattr(app, "send_email_with_pdf", MagicMock(return_value=True))

    def _submit(**overrides):
        app._handle_submit(
            **{**VALID_SUBMISSION, **overrides},
            species_map=sample_species_map,
            breed_map=sample_breed_map,
            sex_map=sample_sex_map,
        )
        return api

    return _submit


def test_valid_submission_sends_the_email(submit, quiet_streamlit):
    """The happy path reaches both the API and the email."""
    api = submit()

    api.assert_called_once()
    app.send_email_with_pdf.assert_called_once()
    assert quiet_streamlit["warning"] == []


def test_missing_zip_code_is_reported_to_the_user(submit, quiet_streamlit, caplog):
    """A rejected submission must not look like a submitted one."""
    with caplog.at_level(logging.INFO, logger="patient_intake"):
        api = submit(zip_code="")

    api.assert_not_called()
    app.send_email_with_pdf.assert_not_called()
    assert quiet_streamlit["warning"] == ["Please enter your ZIP code."]
    assert "Submission rejected by validation: zip_code" in caplog.text


@pytest.mark.parametrize(
    ("field", "value", "logged"),
    [
        ("owner_name", "John", "owner_name"),
        ("cell_no", "555", "phone"),
        ("pet_name", "Fluffy2", "pet_name"),
        ("agree", False, "confirmation"),
    ],
)
def test_validation_failures_are_logged(submit, quiet_streamlit, caplog, field, value, logged):
    """Every rejection names the field in the server-side log."""
    with caplog.at_level(logging.INFO, logger="patient_intake"):
        api = submit(**{field: value})

    api.assert_not_called()
    assert f"Submission rejected by validation: {logged}" in caplog.text
    assert len(quiet_streamlit["warning"]) == 1


def test_unselected_species_is_logged(submit, quiet_streamlit, monkeypatch, caplog):
    """A dropdown that never got a valid id stops the submission."""
    # st.stop() only halts under the Streamlit runtime; outside it, it returns.
    monkeypatch.setattr(app.st, "stop", MagicMock(side_effect=RuntimeError("stopped")))

    with pytest.raises(RuntimeError, match="stopped"):
        with caplog.at_level(logging.INFO, logger="patient_intake"):
            submit(patient_species="Unlisted species")

    assert "no species selected" in caplog.text
    assert quiet_streamlit["error"] == ["Please select a Species."]
