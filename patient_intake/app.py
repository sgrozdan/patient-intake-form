"""Main Streamlit application for patient intake form."""

import re

import streamlit as st

from patient_intake.api_client import fetch_reference_data, submit_patient
from patient_intake.captcha import check_captcha
from patient_intake.email_sender import send_email_with_pdf
from patient_intake.logging_config import configure_logging, get_logger
from patient_intake.pdf_generator import fill_pdf_with_fitz

# Not getLogger(__name__): Streamlit runs this file as __main__.
logger = get_logger("app")

# Streamlit's centred layout caps the content at ~736px, which squeezes two
# columns of fields until the date selectboxes clip their own values. The wide
# layout has no cap at all and sprawls on a large screen, so set one in between.
CONTENT_MAX_WIDTH = "960px"


def _apply_content_width() -> None:
    """Bound the content width, wider than centred but narrower than wide."""
    st.markdown(
        f"""
        <style>
        [data-testid="stMainBlockContainer"], .block-container {{
            max-width: {CONTENT_MAX_WIDTH};
            margin-left: auto;
            margin-right: auto;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def main():
    """Main entry point for the Streamlit application."""
    # Must precede every other Streamlit call. The wide layout drops Streamlit's
    # content cap, which _apply_content_width() then replaces with a wider but
    # still bounded one.
    st.set_page_config(page_title="Patient Intake Form", layout="wide")

    configure_logging()
    _apply_content_width()

    # CAPTCHA check first
    check_captcha()

    # Fetch reference data
    species_map, breed_map, sex_map = fetch_reference_data()

    st.header("Patient Intake Form")
    st.caption("Fields marked with \\* are required.")

    # A form, not loose widgets: outside a form a text input only reaches the
    # server on blur or Enter, so browser autofill - which fills every field at
    # once and focuses none - left the submission looking empty. A form sends
    # the current value of every widget when it is submitted.
    with st.form("intake_form"):
        col1, col2 = st.columns(2)

        # Placeholders rendered next to each field; the submit handler writes
        # validation errors into the matching spot so messages appear inline.
        field_ph: dict = {}

        # === CLIENT AREA ===
        with col1:
            with st.container(border=True):
                st.subheader("Client Information")
                owner_name = st.text_input("Full Name (First and Last): *", key="owner_name")
                st.caption("First and last name, letters only — e.g. Jane Doe")
                field_ph["owner_name"] = st.empty()
                sec_owner_name = st.text_input("Full Name of Secondary Contact:")
                email = st.text_input("Email address: *", key="email")
                st.caption("e.g. name@example.com")
                field_ph["email"] = st.empty()
                cell_no = st.text_input("Phone number (10 digits): *", key="cell_no")
                st.caption(
                    "Exactly 10 digits, numbers only — no spaces or dashes "
                    "(e.g. 5551234567)"
                )
                field_ph["cell_no"] = st.empty()
                work_no = st.text_input("Work phone:")
                alt_no = st.text_input("Alternative phone:")
                employer = st.text_input("Employer:")
                drive_lic = st.text_input("Driver's License (IF writing check):")
                owner_address = st.text_input("Address: *", key="owner_address")
                field_ph["owner_address"] = st.empty()

                city_col, state_col, zip_col = st.columns(3)
                with city_col:
                    city = st.text_input("City *", placeholder="Des Moines", key="city")
                with state_col:
                    state = st.text_input("State *", placeholder="IA", max_chars=2, key="state")
                with zip_col:
                    zip_code = st.text_input(
                        "Zip Code *", placeholder="50309", max_chars=10, key="zip_code"
                    )
                field_ph["city"] = st.empty()
                field_ph["state"] = st.empty()
                field_ph["zip_code"] = st.empty()

                st.markdown("**Owner's Date of Birth**")
                dob_col1, dob_col2, dob_col3 = st.columns(3)
                with dob_col1:
                    owner_day = st.selectbox("Day", list(range(1, 32)))
                with dob_col2:
                    owner_month = st.selectbox("Month", list(range(1, 13)))
                with dob_col3:
                    owner_year = st.selectbox("Year", list(range(1920, 2010)))

                prev_visit = st.selectbox("Have you been to our facility before?", ["Yes", "No"])

        # === ADD CANINE INDEX FOR SPECIES ===
        species_keys = sorted(species_map.keys())
        canine_index = species_keys.index("Canine") if "Canine" in species_keys else 0

        # === PATIENT AREA ===
        with col2:
            with st.container(border=True):
                st.subheader("Pet Information")
                pet_name = st.text_input("Pet Name: *", key="pet_name")
                st.caption("Letters and spaces only")
                field_ph["pet_name"] = st.empty()
                breed_options = sorted(breed_map.keys())
                breed = st.selectbox("Breed *", breed_options, key="breed")
                breed_non_listed = st.text_input("Breed (if not listed):")
                field_ph["breed"] = st.empty()
                color = st.text_input("Color")
                st.markdown("**Patient's Date of Birth**")
                dob_col1, dob_col2, dob_col3 = st.columns(3)
                with dob_col1:
                    day = st.selectbox("Day", list(range(1, 32)), key="pet_day")
                with dob_col2:
                    month = st.selectbox("Month", list(range(1, 13)), key="pet_month")
                with dob_col3:
                    year = st.selectbox("Year", list(range(2000, 2027)), key="pet_year")
                patient_sex = st.selectbox("Sex *", sorted(sex_map.keys()), key="sex")
                field_ph["sex"] = st.empty()
                patient_species = st.selectbox(
                    "Species *", species_keys, index=canine_index, key="species"
                )
                field_ph["species"] = st.empty()
                pet_prev_visit = st.selectbox(
                    "Has this pet been at our facility before?", ["Yes", "No"]
                )

                # PRIMARY CARE VETERINARIAN INFO
                doctor = st.text_input("Doctor")
                clinic_name = st.text_input("Clinic Name")

        agree = st.checkbox("I confirm the information is correct.")
        field_ph["agree"] = st.empty()
        submit_button = st.form_submit_button("Submit")

    # A form hands its values over only when it is submitted, so there is nothing
    # to validate before that: flag the offending fields from the first submission
    # attempt onwards, and re-flag them on every later one.
    field_errors = _validate(
        owner_name=owner_name,
        email=email,
        cell_no=cell_no,
        owner_address=owner_address,
        city=city,
        state=state,
        zip_code=zip_code,
        pet_name=pet_name,
        breed=breed,
        breed_non_listed=breed_non_listed,
        patient_sex=patient_sex,
        patient_species=patient_species,
        agree=agree,
        species_map=species_map,
        breed_map=breed_map,
        sex_map=sex_map,
    )
    if submit_button:
        st.session_state["submit_attempted"] = True
        logger.info("Form submitted")
        if field_errors:
            logger.info("Submission rejected by validation: %s", ", ".join(sorted(field_errors)))

    if st.session_state.get("submit_attempted"):
        _render_field_errors(field_errors, field_ph)

    if submit_button and not field_errors:
        _handle_submit(
            owner_name=owner_name,
            sec_owner_name=sec_owner_name,
            email=email,
            cell_no=cell_no,
            work_no=work_no,
            alt_no=alt_no,
            employer=employer,
            drive_lic=drive_lic,
            owner_address=owner_address,
            city=city,
            state=state,
            zip_code=zip_code,
            owner_day=owner_day,
            owner_month=owner_month,
            owner_year=owner_year,
            prev_visit=prev_visit,
            pet_name=pet_name,
            breed=breed,
            breed_non_listed=breed_non_listed,
            color=color,
            day=day,
            month=month,
            year=year,
            patient_sex=patient_sex,
            patient_species=patient_species,
            pet_prev_visit=pet_prev_visit,
            doctor=doctor,
            clinic_name=clinic_name,
            species_map=species_map,
            breed_map=breed_map,
            sex_map=sex_map,
        )


# Required selectbox fields need a different CSS target than text inputs.
_SELECT_FIELDS = {"breed", "sex", "species"}
_INVALID_COLOR = "#ff4b4b"  # Streamlit's default red


def _render_field_errors(field_errors: dict, field_ph: dict) -> None:
    """Render each validation problem as a compact red line plus a red rounded
    border on the offending field.

    The border is applied via the ``st-key-<key>`` wrapper class Streamlit adds to
    every keyed widget, so each field is targeted without positional selectors.
    """
    css_rules = []
    for key, message in field_errors.items():
        placeholder = field_ph.get(key)
        if placeholder is not None:
            placeholder.markdown(f":red[⚠ {message}]")
        if key in _SELECT_FIELDS:
            css_rules.append(
                f'.st-key-{key} [data-baseweb="select"] > div '
                f"{{ border-color:{_INVALID_COLOR} !important; "
                "border-radius:0.5rem !important; }"
            )
        elif key != "agree":  # checkbox: compact text only, no border
            css_rules.append(
                f'.st-key-{key} [data-baseweb="input"] '
                f"{{ border:1px solid {_INVALID_COLOR} !important; "
                "border-radius:0.5rem !important; }"
            )
    if css_rules:
        st.markdown("<style>" + "".join(css_rules) + "</style>", unsafe_allow_html=True)


def _validate(
    owner_name: str,
    email: str,
    cell_no: str,
    owner_address: str,
    city: str,
    state: str,
    zip_code: str,
    pet_name: str,
    breed: str,
    breed_non_listed: str,
    patient_sex: str,
    patient_species: str,
    agree: bool,
    species_map: dict,
    breed_map: dict,
    sex_map: dict,
) -> dict:
    """Validate the form and return a {field key -> message} dict of problems.

    Run on every render so empty/invalid required fields are flagged inline,
    not only after the user clicks Submit.
    """
    # field key -> message; each message is rendered inline next to its field.
    field_errors: dict[str, str] = {}

    species_id = species_map.get(patient_species)
    breed_id = breed_map.get(breed)
    sex_id = sex_map.get(patient_sex)

    # --- Owner information ---
    if not owner_name.strip():
        field_errors["owner_name"] = "Full Name is required."
    elif not re.fullmatch(r"[A-Za-z'-]+ [A-Za-z'-]+([A-Za-z'-]+)*", owner_name):
        field_errors["owner_name"] = (
            "Enter first and last name using letters only — e.g. Jane Doe."
        )

    if not email.strip():
        field_errors["email"] = "Email address is required."
    elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        field_errors["email"] = "Enter a valid email address — e.g. name@example.com."

    if not cell_no.strip():
        field_errors["cell_no"] = "Phone number is required."
    elif not re.fullmatch(r"\d{10}", cell_no):
        field_errors["cell_no"] = (
            "Phone must be exactly 10 digits, numbers only — e.g. 5551234567 "
            "(no spaces, dashes, or parentheses)."
        )

    if not owner_address.strip():
        field_errors["owner_address"] = "Address is required."

    if not city.strip():
        field_errors["city"] = "City is required."

    if not state.strip():
        field_errors["state"] = "State is required."
    elif not re.fullmatch(r"[A-Za-z]{2}", state):
        field_errors["state"] = "Use the 2-letter state code — e.g. IA."

    if not zip_code.strip():
        field_errors["zip_code"] = "Zip Code is required."
    elif not re.fullmatch(r"\d{5}(-\d{4})?", zip_code.strip()):
        field_errors["zip_code"] = "Enter a 5-digit ZIP code — e.g. 50309."

    # --- Pet information ---
    if not pet_name.strip():
        field_errors["pet_name"] = "Pet Name is required."
    elif not re.fullmatch(r"[A-Za-z ]+", pet_name):
        field_errors["pet_name"] = "Pet Name can contain letters and spaces only."

    if species_id is None:
        field_errors["species"] = "Please select a Species."
    if sex_id is None:
        field_errors["sex"] = "Please select Sex."
    if breed_id is None and not breed_non_listed.strip():
        field_errors["breed"] = "Select a Breed or fill 'Breed (if not listed)'."

    # --- Confirmation ---
    if not agree:
        field_errors["agree"] = "Please check the confirmation box."

    return field_errors


def _handle_submit(
    owner_name: str,
    sec_owner_name: str,
    email: str,
    cell_no: str,
    work_no: str,
    alt_no: str,
    employer: str,
    drive_lic: str,
    owner_address: str,
    city: str,
    state: str,
    zip_code: str,
    owner_day: int,
    owner_month: int,
    owner_year: int,
    prev_visit: str,
    pet_name: str,
    breed: str,
    breed_non_listed: str,
    color: str,
    day: int,
    month: int,
    year: int,
    patient_sex: str,
    patient_species: str,
    pet_prev_visit: str,
    doctor: str,
    clinic_name: str,
    species_map: dict,
    breed_map: dict,
    sex_map: dict,
):
    """Submit a validated form: build the payload, call the API, email the PDF."""
    species_id = species_map.get(patient_species)
    breed_id = breed_map.get(breed)
    sex_id = sex_map.get(patient_sex)

    first, last = owner_name.split(" ", 1)

    payload = {
        "company_id": 1,
        "patient_name": pet_name,
        "patient_species": species_id,
        "patient_breed": breed_id if breed_id is not None else None,
        "patient_sex": sex_id,
        "birthday_day": day,
        "birthday_month": month,
        "birthday_year": year,
        "patient_owner_firstname": first,
        "patient_owner_lastname": last,
        "patient_address": owner_address,
        "patient_email": email,
        "patient_phone": cell_no,
        "address": owner_address,
        "email": email,
        "phone": cell_no,
        "city": city,
        "state": state,
        "zip": zip_code,
    }

    st.write("DEBUG IDs", {"species_id": species_id, "breed_id": breed_id, "sex_id": sex_id})

    try:
        response = submit_patient(payload)
        st.write("DEBUG status:", response.status_code)
        try:
            result = response.json()
            st.write("DEBUG json:", result)
        except Exception:
            st.write("DEBUG text:", response.text[:400])
            st.error("Server did not return JSON.")
            st.stop()

        if response.status_code == 200 and result.get("result") == "success":
            # Collect extra fields for PDF/Email
            sec_first, sec_last = ("", "")
            if sec_owner_name and " " in sec_owner_name:
                sec_first, sec_last = sec_owner_name.split(" ", 1)
            elif sec_owner_name:
                sec_first = sec_owner_name

            extra_fields = {
                "sec_owner_firstname": sec_first,
                "sec_owner_lastname": sec_last,
                "work_no": work_no,
                "alt_no": alt_no,
                "employer": employer,
                "drive_lic": drive_lic,
                "owner_day": owner_day,
                "owner_month": owner_month,
                "owner_year": owner_year,
                "prev_visit": prev_visit,
                "color": color,
                "breed_not_listed": breed_non_listed,
                "pet_prev_visit": pet_prev_visit,
                "doctor": doctor,
                "clinic_name": clinic_name,
            }

            pdf_filled = fill_pdf_with_fitz(
                payload, extra_fields, species_map, breed_map, sex_map
            )
            ok = send_email_with_pdf(
                pdf_bytes=pdf_filled.getvalue(),
                filename=f"{payload['patient_name']}_intake_form.pdf",
                patient_name=payload["patient_name"],
                payload=payload,
                extra_fields=extra_fields,
                species_map=species_map,
                breed_map=breed_map,
                sex_map=sex_map,
            )
            if not ok:
                st.warning("Patient saved; email failed (see error above).")

            logger.info(
                "Patient created: id=%s, email sent=%s", result.get("patient_id", "?"), ok
            )
            st.success(f"Patient uploaded successfully! ID: {result.get('patient_id', '?')}")
            st.balloons()
        else:
            st.error(f"API Error: {result.get('message', response.text)}")
            st.stop()

    except Exception as e:
        logger.exception("Patient submission failed")
        st.error(f"Request failed: {e}")
        st.stop()


if __name__ == "__main__":
    main()
