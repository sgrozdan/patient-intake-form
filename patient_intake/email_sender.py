"""Email sending functionality for patient intake forms."""

import logging
import os
import smtplib
from email.message import EmailMessage

import streamlit as st

from patient_intake.config import get_email_config
from patient_intake.logging_config import mask

# Without a timeout a dropped connection blocks the form until the user retries
# and creates a duplicate patient.
SMTP_TIMEOUT = 30

logger = logging.getLogger(__name__)


def _smtp_debug_level() -> int:
    """Return smtplib's debug level, enabled with SMTP_DEBUG.

    The trace shows the whole SMTP dialogue, including the accepting response
    with the provider's message id - and the AUTH exchange, which carries the
    base64-encoded credentials. Hence opt-in only.
    """
    return 1 if os.environ.get("SMTP_DEBUG", "").lower() in ("1", "true", "yes") else 0


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
        logger.info(
            "Sending intake email for %r via %s:%s, login %s, from %s to %s",
            patient_name,
            email_config["smtp_server"],
            email_config["smtp_port"],
            mask(email_config["smtp_login"]),
            email_config["sender_email"],
            email_config["recipient_email"],
        )
        debug_level = _smtp_debug_level()
        if debug_level:
            logger.warning(
                "SMTP_DEBUG is on: the protocol trace on stderr includes the "
                "base64-encoded credentials. Turn it off once diagnosed."
            )
        with smtplib.SMTP(
            email_config["smtp_server"], email_config["smtp_port"], timeout=SMTP_TIMEOUT
        ) as server:
            server.set_debuglevel(debug_level)
            server.starttls()
            server.login(email_config["smtp_login"], email_config["sender_password"])
            refused = server.send_message(msg)
        if refused:
            # The server took the message but dropped recipients from it.
            logger.warning("SMTP server refused recipients: %s", refused)
        else:
            logger.info(
                "Intake email for %r accepted by %s", patient_name, email_config["smtp_server"]
            )
        return True
    except Exception:
        logger.exception("Sending intake email failed")
        st.error("Email delivery failed - the form was saved, please notify the clinic.")
        return False
