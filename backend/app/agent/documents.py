"""Which documents a claim must carry, named with the DHA HIE attachment document types.

SHA Part A 13.3.1 says each claim is supported by "the documentation prescribed by the
Authority for the relevant Fund and service line". On the HIE that list is read from each
intervention's `applicableDocumentTypes`, and a claim with several interventions needs the
union of them. Until Lipwad reads interventions, BASELINE holds the three documents every
claim carries: a claim form, an itemised invoice or final bill, and a discharge or case
summary.
"""

from collections.abc import Iterable
from dataclasses import dataclass

# DHA HIE claim attachment `document_type` values for the files Lipwad reads today.
FILE_TYPES = {
    "claim_form.png": "CLAIM_FORM",
    "invoice.png": "INVOICE",
    "discharge_summary.png": "DISCHARGE_SUMMARY",
    "case_summary.png": "CASE_SUMMARY",
}


@dataclass(frozen=True)
class Requirement:
    """One required document, satisfied by any of the listed HIE document types."""

    label: str
    any_of: tuple[str, ...]
    code: str
    rule_id: str = "SHA-A-13.3.1-SUPPORTING-DOCS"


BASELINE = (
    Requirement("claim form", ("CLAIM_FORM",), "claim_form_missing", "SHI-REG-58-FORM3"),
    Requirement("itemised invoice or final bill", ("INVOICE", "FINAL_BILL"), "invoice_missing"),
    Requirement(
        "discharge or case summary",
        ("DISCHARGE_SUMMARY", "CASE_SUMMARY"),
        "discharge_summary_missing",
    ),
)


def required_documents(interventions: Iterable[Iterable[str]] | None = None) -> list[Requirement]:
    """The documents a claim needs.

    `interventions` takes each intervention's `applicableDocumentTypes` from the HIE. When
    given, their union replaces the baseline; without them, the baseline applies.
    """
    if interventions is None:
        return list(BASELINE)
    union = sorted({kind for needs in interventions for kind in needs})
    return [
        Requirement(kind.lower().replace("_", " "), (kind,), f"{kind.lower()}_missing")
        for kind in union
    ]


def present_types(filenames: Iterable[str]) -> set[str]:
    return {FILE_TYPES[name] for name in filenames if name in FILE_TYPES}


def missing(present: set[str], requirements: Iterable[Requirement]) -> list[Requirement]:
    return [r for r in requirements if not present.intersection(r.any_of)]
