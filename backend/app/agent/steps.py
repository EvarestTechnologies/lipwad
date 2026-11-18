"""What a person does about each finding, in plain words.

The same wording feeds Today, the What to fix panel and the explanation model, so the
model only restates steps Lipwad has already chosen. None of them names a value, picks
which document is right, or asks anyone to add, remove or change a charge or a code.
"""

FIX_STEPS = {
    "discharge_summary_missing": "Attach the discharge or case summary.",
    "claim_form_missing": "Attach the claim form.",
    "invoice_missing": "Attach the itemised invoice or final bill.",
    "itemised_invoice_missing": "Attach an invoice that lists each service with its price.",
    "declaration_unsigned": "Get the hospital declaration signed, then attach the signed page.",
    "facility_stamp_missing": "Stamp the claim form, then attach it again.",
    "physician_details_missing": (
        "Add the rendering physician's name and registration number to the claim form."
    ),
    "discharge_summary_unsigned": (
        "Ask the treating clinician to sign the discharge summary, then attach it."
    ),
    "service_type_inconsistent": (
        "Check the visit type and the billed bed days with the ward, and correct the "
        "document that is wrong."
    ),
    "practitioner_not_found": "Confirm the practitioner's registration number with the ward.",
    "admission_date_mismatch": (
        "Confirm the admission date with the ward, and correct the document that is wrong."
    ),
    "retake_required": "Retake the photo in better light.",
    "voice_note_unclear": "Record the voice note again somewhere quiet.",
    "voice_needs_review": (
        "Listen to the part of the voice note that is not in English and enter the details "
        "yourself."
    ),
    "resubmission_deadline_near": (
        "Fix the sent back claim and resubmit it within 14 days of the date it was returned."
    ),
    "claim_rejected": (
        "SHA rejected this claim; a review can be requested with new evidence within 7 "
        "working days."
    ),
}
