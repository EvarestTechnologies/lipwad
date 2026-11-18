"""Rule checks over a claim's cited fields.

Every finding cites its evidence and a rule from RULES. Each rule records the document
it comes from, that document's status and the exact words of the clause, as registered
in docs/SOURCES.md. Rules marked "lipwad" are Lipwad's own evidence checks, never SHA
rules.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from app.db.schemas import Citation, Claim, Field, Flag, Lifecycle

DEADLINE_WARNING = timedelta(hours=48)

PART_A = "https://www.sha.go.ke/wp-content/uploads/2026/10/PART-A-Master-General-Terms-and-Conditions_1.pdf"
PART_B2 = "https://www.sha.go.ke/wp-content/uploads/2026/10/PART-B2-Social-Health-Insurance-Fund-Contract-1.pdf"
LN_49 = "https://new.kenyalaw.org/akn/ke/act/ln/2024/49/eng@2025-02-28"


@dataclass(frozen=True)
class Source:
    """A rule and the registered document it comes from."""

    title: str
    issuer: str
    version: str
    status: Literal["final", "news", "lipwad"]
    url: str
    clause: str
    quote: str
    checks: str


_PART_A = dict(
    title="Contract for the Provision of Healthcare Services, Part A, Master General Terms and "
    "Conditions",
    issuer="Social Health Authority",
    version="Part A, 16 Oct 2026",
    status="final",
    url=PART_A,
)
_LN_49 = dict(
    title="The Social Health Insurance Regulations, 2024 (Legal Notice 49 of 2024)",
    issuer="Cabinet Secretary for Health",
    version="LN 49 of 2024",
    status="final",
    url=LN_49,
)

RULES: dict[str, Source] = {
    "SHA-A-13.2.1-SUBMIT-7D": Source(
        **_PART_A,
        clause="13.2.1, p. 52",
        quote="The Healthcare Provider shall submit all its Claims electronically to the "
        "Authority or its appointed agent within seven (7) days of the date of Service or of "
        "the date of discharge of the Beneficiary, whichever is later.",
        checks="Shows the submission deadline, seven days after discharge.",
    ),
    "SHA-A-13.1.2-ACCURATE": Source(
        **_PART_A,
        clause="13.1.2, p. 52",
        quote="The Healthcare Provider certifies that all data submitted in relation to a "
        "Beneficiary shall at all times be accurate, complete and truthful.",
        checks="Flags documents that disagree: bed days billed on an outpatient or same-day "
        "visit, or a voice note admission date that differs from the claim form.",
    ),
    "SHA-A-13.3.1-SUPPORTING-DOCS": Source(
        **_PART_A,
        clause="13.3.1, p. 53",
        quote="Each Claim shall be supported by the documentation prescribed by the Authority "
        "for the relevant Fund and service line, including the beneficiary verification "
        "reference, the pre-authorisation reference where applicable, the discharge summary, "
        "the Care Plan, the medical report, the itemised invoice coded to the Tariff, the "
        "treatment sheet and medication chart, investigation requests and results, operation "
        "notes where a procedure was performed, and referral documents where applicable.",
        checks="Flags a missing required document, or an invoice that shows a total without "
        "separate priced lines.",
    ),
    "SHA-A-13.4.3-LICENSED": Source(
        **_PART_A,
        clause="13.4.3, pp. 53-54",
        quote="The Healthcare Provider shall not submit a Claim which involves ... a Service "
        "delivered by a person not licensed or authorised to deliver it",
        checks="Flags a practitioner number the registry lookup does not find.",
    ),
    "SHA-A-13.5.2-RESUBMIT-14D": Source(
        **_PART_A,
        clause="13.5.2, p. 54",
        quote="The Healthcare Provider shall correct and resubmit a Sent Back Claim within "
        "fourteen (14) days of the date on which it was returned. A Sent Back Claim which is "
        "not resubmitted within that period shall lapse and shall not be payable.",
        checks="Counts down the 14 days to resubmit a sent back claim.",
    ),
    "SHA-A-13.8.1-REVIEW-7WD": Source(
        **_PART_A,
        clause="13.8.1, p. 55",
        quote="A Healthcare Provider aggrieved by the rejection or reduction of a Claim may, "
        "with new evidence, request a review by the Authority within seven (7) Working Days "
        "of notification.",
        checks="Flags a rejected claim and its seven working day review window.",
    ),
    "SHA-B2-SHIF-DOCS": Source(
        title="Contract for the Provision of Healthcare Services, Part B2, Social Health "
        "Insurance Fund Contract",
        issuer="Social Health Authority",
        version="Part B2, 16 Oct 2026",
        status="final",
        url=PART_B2,
        clause="8.1.2, p. 11",
        quote="... the itemised invoice coded to the Tariff, and the discharge summary signed "
        "by the treating Healthcare Professional.",
        checks="Flags an SHIF inpatient discharge summary with no clinician signature.",
    ),
    "SHI-REG-58-LODGE-7D": Source(
        **_LN_49,
        clause="reg. 58(1)",
        quote="A healthcare provider or health facility shall, within seven days from the date "
        "of discharge of the patient, lodge a claim to the Claims Management Office or a "
        "medical insurance provider and claim settling agent, where applicable, for review and "
        "processing of the claim.",
        checks="Shows the submission deadline, seven days after discharge.",
    ),
    "SHI-FORM3-FIELDS": Source(
        **_LN_49,
        clause="First Schedule, Form 3",
        quote="All fields in this form are mandatory. Incomplete forms will not be processed.",
        checks="Flags a claim form read as having no clinician signature.",
    ),
    "SHI-SCHED-INPATIENT-LEVEL": Source(
        **_LN_49,
        clause="Second and Third Schedules",
        quote='Primary Healthcare Fund inpatient point of access "Level 2-4". Social Health '
        'Insurance Fund inpatient point of access "Level 4 - 6".',
        checks="Registered for the fund and facility-level checks planned in Phase 2. Nothing "
        "is flagged against it yet.",
    ),
    "DHA-HIE-REQUIRED-DOCS": Source(
        title="Understanding Virtual Claims",
        issuer="Digital Health Agency, HIE documentation",
        version="last modified 28 Sep 2026",
        status="final",
        url="https://hie-docs.dha.go.ke/docs/claims/guides/understandingClaims",
        clause="Provider Claim field reference, note",
        quote="If any required document is missing, the claim submission will be blocked.",
        checks="Context for the required-documents check: the HIE blocks incomplete claims.",
    ),
    "SHA-NEWS-3-DOCS": Source(
        title="SHA halts Ksh3B claims and issues 14-day ultimatum",
        issuer="People Daily (Kenneth Mwenda)",
        version="15 Sep 2025",
        status="news",
        url="https://peopledaily.digital/news/sha-halts-ksh3b-claims-and-issues-14-day-ultimatum",
        clause="news report",
        quote="According to SHA, every claim must include three mandatory documents: a duly "
        "filled claim form, an itemised invoice, and a discharge or case summary.",
        checks="Context only for the required-documents check. Never cited alone.",
    ),
    "LIPWAD-EVIDENCE-QUALITY": Source(
        title="Lipwad evidence check",
        issuer="Lipwad",
        version="Lipwad check",
        status="lipwad",
        url="",
        clause="",
        quote="Lipwad does not read a value it cannot see or hear clearly. It asks a person "
        "to retake the photo, record the note again, or review it. This is Lipwad's own "
        "check, not an SHA rule.",
        checks="Flags an unreadable photo or a voice note that could not be heard or needs "
        "human review.",
    ),
    "LIPWAD-CODING-PENDING": Source(
        title="Lipwad coding status",
        issuer="Lipwad",
        version="Lipwad check",
        status="lipwad",
        url="",
        clause="",
        quote="Lipwad does not assign service or diagnosis codes yet. SHA's coding standard "
        "is not confirmed, so every claim shows its service as not coded. This is Lipwad's "
        "own note, not an SHA rule.",
        checks="Marks the service as not coded until coding is built in Phase 2.",
    ),
}


def rule(rule_id: str) -> Citation:
    if rule_id not in RULES:
        raise KeyError(f"{rule_id} is not in the rules catalogue")
    source = RULES[rule_id]
    return Citation(kind="rule", source_id=rule_id, rule_version=source.version, quote=source.quote)


@dataclass
class Evidence:
    fields: dict[str, Field]
    retake_reasons: list[str]
    practitioner_found: bool | None
    voice_retake: Citation | None = None


def check(claim: Claim, evidence: Evidence, now: datetime) -> list[Flag]:
    fields, flags = evidence.fields, []

    def cite(*names: str) -> list[Citation]:
        return [c for name in names if name in fields for c in fields[name].citations]

    if evidence.retake_reasons:
        page = Citation(kind="image", source_id=claim.id + "-claim_form", region=[[0, 0], [1, 1]])
        retake = cite("patient_ref", "admission_date") or [page]
        flags.append(
            Flag(
                code="retake_required",
                severity="amber",
                citations=[*retake, rule("LIPWAD-EVIDENCE-QUALITY")],
            )
        )
    if evidence.voice_retake:
        flags.append(
            Flag(
                code="voice_note_unclear",
                severity="amber",
                citations=[evidence.voice_retake, rule("LIPWAD-EVIDENCE-QUALITY")],
            )
        )
    if fields.get("clinician_signature") and fields["clinician_signature"].value == "absent":
        flags.append(
            Flag(
                code="signature_missing",
                severity="amber",
                citations=[*cite("clinician_signature"), rule("SHI-FORM3-FIELDS")],
            )
        )
    if fields.get("invoice_itemised") and fields["invoice_itemised"].value == "no":
        flags.append(
            Flag(
                code="itemised_invoice_missing",
                severity="amber",
                citations=[*cite("invoice_itemised"), rule("SHA-A-13.3.1-SUPPORTING-DOCS")],
            )
        )
    spoken, written = fields.get("voice_admission_date"), fields.get("admission_date")
    if spoken and written and spoken.value != written.value:
        flags.append(
            Flag(
                code="admission_date_mismatch",
                severity="amber",
                citations=[
                    *cite("admission_date", "voice_admission_date"),
                    rule("SHA-A-13.1.2-ACCURATE"),
                ],
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
                citations=[*cite("visit_type", *bed_lines), rule("SHA-A-13.1.2-ACCURATE")],
            )
        )
    if evidence.practitioner_found is False:
        flags.append(
            Flag(
                code="practitioner_not_found",
                severity="red",
                citations=[*cite("practitioner_id"), rule("SHA-A-13.4.3-LICENSED")],
            )
        )
    if claim.lifecycle is Lifecycle.REJECTED:
        flags.append(
            Flag(
                code="claim_rejected", severity="amber", citations=[rule("SHA-A-13.8.1-REVIEW-7WD")]
            )
        )
    deadline = claim.resubmission_deadline
    if deadline and deadline - now <= DEADLINE_WARNING:
        flags.append(
            Flag(
                code="resubmission_deadline_near",
                severity="amber",
                citations=[rule("SHA-A-13.5.2-RESUBMIT-14D")],
            )
        )
    return flags
