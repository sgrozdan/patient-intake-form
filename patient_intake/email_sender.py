"""Email sending functionality for patient intake forms."""

import smtplib
from email.message import EmailMessage

import streamlit as st

from patient_intake.config import get_email_config

# Without a timeout a dropped connection blocks the form until the user retries
# and creates a duplicate patient.
SMTP_TIMEOUT = 30


def label_from_id(mapping: dict, _id, default: str = "") -> str:
    """Invert the mapping safely to get the label for a given id."""
    inv = {v: k for k, v in mapping.items()}
    return inv.get(_id, default)


def format_email_body(
    payload: dict, extra_fields: dict, species_map: dict, breed_map: dict, sex_map: dict
) -> str:
    """Format the email body with form data."""
    species_label = label_from_id(species_map, payload.get("patient_species"))
    breed_label = label_from_id(breed_map, payload.get("patient_breed"))
    sex_label = label_from_id(sex_map, payload.get("patient_sex"))

    lines = []
    lines.append("**Owner Information**")
    lines.append(
        f"Name: {payload.get('patient_owner_firstname', '')} "
        f"{payload.get('patient_owner_lastname', '')}"
    )
    lines.append(
        f"Secondary Contact: {extra_fields.get('sec_owner_firstname', '')} "
        f"{extra_fields.get('sec_owner_lastname', '')}"
    )
    lines.append(f"Address: {payload.get('patient_address', '')}")
    lines.append(
        f"City/State/ZIP: {payload.get('city', '')}, "
        f"{payload.get('state', '')} {payload.get('zip', '')}"
    )
    lines.append(f"Phone: {payload.get('phone', '')}")
    lines.append(f"Email: {payload.get('email', '')}")
    lines.append(f"Work Phone: {extra_fields.get('work_no', '')}")
    lines.append(f"Alt Phone: {extra_fields.get('alt_no', '')}")
    lines.append(f"Employer: {extra_fields.get('employer', '')}")
    lines.append(f"Driver's License: {extra_fields.get('drive_lic', '')}")
    lines.append(
        f"DOB: {extra_fields.get('owner_month')}/"
        f"{extra_fields.get('owner_day')}/{extra_fields.get('owner_year')}"
    )
    lines.append(f"Previous Client: {extra_fields.get('prev_visit')}")

    lines.append("\n**Patient Information**")
    lines.append(f"Pet Name: {payload['patient_name']}")
    lines.append(f"Species: {species_label}")
    lines.append(f"Breed: {breed_label}")
    lines.append(f"Breed (if not listed): {extra_fields.get('breed_not_listed', '')}")
    lines.append(f"Sex: {sex_label}")
    lines.append(f"Color: {extra_fields.get('color', '')}")
    lines.append(
        f"Birthday: {payload['birthday_month']}/"
        f"{payload['birthday_day']}/{payload['birthday_year']}"
    )
    lines.append(f"Seen Before: {extra_fields.get('pet_prev_visit')}")

    lines.append("\n**Referring Veterinarian**")
    lines.append(f"Doctor: {extra_fields.get('doctor', '')}")
    lines.append(f"Clinic: {extra_fields.get('clinic_name', '')}")
    return "\n".join(lines)


def send_email_with_pdf(
    pdf_bytes: bytes,
    filename: str,
    patient_name: str,
    payload: dict,
    extra_fields: dict,
    species_map: dict,
    breed_map: dict,
    sex_map: dict,
) -> bool:
    """Send email with PDF attachment."""
    try:
        # Inside the try: a misconfiguration must be reported as a failed email,
        # not as a failed submission - the patient has already been created.
        email_config = get_email_config()
        msg = EmailMessage()
        msg["Subject"] = f"New Patient Intake: {patient_name}"
        msg["From"] = email_config["sender_email"]
        msg["To"] = email_config["recipient_email"]
        msg.set_content(
            format_email_body(payload, extra_fields, species_map, breed_map, sex_map)
        )
        msg.add_attachment(
            pdf_bytes, maintype="application", subtype="pdf", filename=filename
        )
        with smtplib.SMTP(
            email_config["smtp_server"], email_config["smtp_port"], timeout=SMTP_TIMEOUT
        ) as server:
            server.starttls()
            server.login(email_config["smtp_login"], email_config["sender_password"])
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Email compose/send failed: {e}")
        return False
