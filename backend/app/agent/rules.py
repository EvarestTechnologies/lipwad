"""Rule checks over a claim's cited fields.

Rule IDs are placeholders until docs/SOURCES.md registers the SHA documents they come
from; each finding cites both the evidence and the placeholder rule version.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.db.schemas import Citation, Claim, Field, Flag, Lifecycle

RULE_VERSION = "v[PLACEHOLDER]"
DEADLINE_WARNING = timedelta(hours=48)
MIN_INPATIENT_LEVEL = 3

# What each check looks at, in Lipwad's own words. This is not SHA rule text; the
# source documents are not yet registered in docs/SOURCES.md.
RULES = {
    "SHA-DOC-SIGNATURE": "The claim form carries the clinician's signature.",
    "SHA-DOC-INVOICE": "The invoice lists each service with its own price.",
    "SHA-SERVICE-TYPE": "Billed services match the visit type on the claim form.",
    "SHA-PRACTITIONER-REGISTRY": "The practitioner number is in the practitioner registry.",
    "SHA-FACILITY-LEVEL": "Inpatient care is billed only at a facility level that offers it.",
    "SHA-RESUBMISSION": "A returned or rejected claim is resubmitted within 14 days.",
    "TERM-PLACEHOLDER": "Each service carries a code from the SHA terminology.",
}


def rule(rule_id: str) -> Citation:
    if rule_id not in RULES:
        raise KeyError(f"{rule_id} is not in the rules catalogue")
    return Citation(kind="rule", source_id=rule_id, rule_version=RULE_VERSION)


@dataclass
class Evidence:
    fields: dict[str, Field]
    retake_reasons: list[str]
    practitioner_found: bool | None
    facility_level: int | None


def check(claim: Claim, evidence: Evidence, now: datetime) -> list[Flag]:
    fields, flags = evidence.fields, []

    def cite(*names: str) -> list[Citation]:
        return [c for name in names if name in fields for c in fields[name].citations]

    if evidence.retake_reasons:
        page = Citation(kind="image", source_id=claim.id + "-claim_form", region=[[0, 0], [1, 1]])
        retake = cite("patient_ref", "admission_date") or [page]
        flags.append(Flag(code="retake_required", severity="amber", citations=retake))
    if fields.get("clinician_signature") and fields["clinician_signature"].value == "absent":
        flags.append(
            Flag(
                code="signature_missing",
                severity="amber",
                citations=[*cite("clinician_signature"), rule("SHA-DOC-SIGNATURE")],
            )
        )
    if fields.get("invoice_itemised") and fields["invoice_itemised"].value == "no":
        flags.append(
            Flag(
                code="itemised_invoice_missing",
                severity="amber",
                citations=[*cite("invoice_itemised"), rule("SHA-DOC-INVOICE")],
            )
        )
    bed_lines = [
        name
        for name, item in fields.items()
        if name.startswith("invoice_line") and re.search(r"\bbed[ -]?days?\b", item.value, re.I)
    ]
    visit = fields.get("visit_type")
    same_day = (
        fields.get("admission_date")
        and fields.get("discharge_date")
        and (fields["admission_date"].value == fields["discharge_date"].value)
    )
    outpatient = bool(visit and re.search(r"\bout-?patient\b", visit.value, re.I))
    if bed_lines and (outpatient or same_day):
        flags.append(
            Flag(
                code="service_type_inconsistent",
                severity="red",
                citations=[*cite("visit_type", *bed_lines), rule("SHA-SERVICE-TYPE")],
            )
        )
    if evidence.practitioner_found is False:
        flags.append(
            Flag(
                code="practitioner_not_found",
                severity="red",
                citations=[*cite("practitioner_id"), rule("SHA-PRACTITIONER-REGISTRY")],
            )
        )
    inpatient = bool(visit and re.search(r"\bin-?patient\b", visit.value, re.I))
    if (
        inpatient
        and evidence.facility_level is not None
        and evidence.facility_level < MIN_INPATIENT_LEVEL
    ):
        flags.append(
            Flag(
                code="service_outside_facility_level",
                severity="red",
                citations=[*cite("visit_type", "facility_id"), rule("SHA-FACILITY-LEVEL")],
            )
        )
    if claim.lifecycle is Lifecycle.REJECTED:
        flags.append(
            Flag(code="claim_rejected", severity="amber", citations=[rule("SHA-RESUBMISSION")])
        )
    deadline = claim.resubmission_deadline
    if deadline and deadline - now <= DEADLINE_WARNING:
        flags.append(
            Flag(
                code="resubmission_deadline_near",
                severity="amber",
                citations=[rule("SHA-RESUBMISSION")],
            )
        )
    return flags
