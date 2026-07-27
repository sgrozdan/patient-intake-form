"""Main Streamlit application for patient intake form."""

import logging
import re

import streamlit as st

from patient_intake.api_client import fetch_reference_data, submit_patient
from patient_intake.captcha import check_captcha
from patient_intake.email_sender import send_email_with_pdf
from patient_intake.logging_config import configure_logging
from patient_intake.pdf_generator import fill_pdf_with_fitz

logger = logging.getLogger(__name__)


def main():
    """Main entry point for the Streamlit application."""
    configure_logging()

    # CAPTCHA check first
    check_captcha()

    # Fetch reference data
    species_map, breed_map, sex_map = fetch_reference_data()

    # === UI FORM ===
    st.markdown(
        """
    <style>
    .responsive-box {
        width: 100%;
        max-width: 480px;
        padding: 1rem;
        border: 1px solid #CCC;
        border-radius: 10px;
        background-color: #f9f9f9;
        margin: 0 auto;
    }
    @media screen and (max-width: 768px) { .responsive-box { max-width: 100%; } }
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.header("Patient Intake Form")

    col1, col2 = st.columns(2)

    # === CLIENT AREA ===
    with col1:
        with st.container(border=True):
            st.subheader("Client Information")
            owner_name = st.text_input("Full Name (First and Last):")
            sec_owner_name = st.text_input("Full Name of Secondary Contact:")
            email = st.text_input("Email address:")
            cell_no = st.text_input("Phone number (10 digits):")
            work_no = st.text_input("Work phone:")
            alt_no = st.text_input("Alternative phone:")
            employer = st.text_input("Employer:")
            drive_lic = st.text_input("Driver's License (IF writing check):")
            owner_address = st.text_input("Address:")

            city_col, state_col, zip_col = st.columns(3)
            with city_col:
                city = st.text_input("City:")
            with state_col:
                state = st.text_input("State (2-letter):")
            with zip_col:
                zip_code = st.text_input("Zip Code:")

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
            pet_name = st.text_input("Pet Name:")
            breed_options = sorted(breed_map.keys())
            breed = st.selectbox("Breed", breed_options)
            breed_non_listed = st.text_input("Breed (if not listed):")
            color = st.text_input("Color")
            st.markdown("**Patient's Date of Birth**")
            dob_col1, dob_col2, dob_col3 = st.columns(3)
            with dob_col1:
                day = st.selectbox("Day", list(range(1, 32)), key="pet_day")
            with dob_col2:
                month = st.selectbox("Month", list(range(1, 13)), key="pet_month")
            with dob_col3:
                year = st.selectbox("Year", list(range(2000, 2027)), key="pet_year")
            patient_sex = st.selectbox("Sex", sorted(sex_map.keys()))
            patient_species = st.selectbox("Species", species_keys, index=canine_index)
            pet_prev_visit = st.selectbox(
                "Has this pet been at our facility before?", ["Yes", "No"]
            )

            # PRIMARY CARE VETERINARIAN INFO
            doctor = st.text_input("Doctor")
            clinic_name = st.text_input("Clinic Name")

    agree = st.checkbox("I confirm the information is correct.")
    submit_button = st.button("Submit")

    if submit_button:
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
            agree=agree,
            species_map=species_map,
            breed_map=breed_map,
            sex_map=sex_map,
        )


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
    agree: bool,
    species_map: dict,
    breed_map: dict,
    sex_map: dict,
):
    """Handle form submission."""
    all_valid = True
    st.write("Form submitted")

    if not re.fullmatch(r"[A-Za-z'-]+ [A-Za-z'-]+([A-Za-z'-]+)*", owner_name):
        st.warning("Please enter your full name (first and last).")
        all_valid = False

    if not re.fullmatch(r"\d{10}", cell_no):
        st.warning("Please enter a valid phone number (10 digits only).")
        all_valid = False

    if not re.fullmatch(r"[A-Za-z ]+", pet_name):
        st.warning("Please enter a valid pet name (letters and spaces only).")
        all_valid = False

    if not agree:
        st.warning("Please check the confirmation box.")
        all_valid = False

    if not zip_code:
        all_valid = False

    if not all_valid:
        return

    first, last = owner_name.split(" ", 1)

    # Validate dropdowns to ensure IDs exist
    species_id = species_map.get(patient_species)
    breed_id = breed_map.get(breed)
    sex_id = sex_map.get(patient_sex)

    if species_id is None:
        st.error("Please select a Species.")
        st.stop()
    if sex_id is None:
        st.error("Please select Sex.")
        st.stop()
    if breed_id is None and not breed_non_listed.strip():
        st.error("Please select a Breed or fill 'Breed (if not listed)'.")
        st.stop()

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
