from pathlib import Path

import pytest

from app.db.schemas import Upload
from app.models import Role, StubProvider
from app.tools.fixtures import load_fixtures
from app.tools.intake import DocumentInput, extract_document

DATA_DIR = Path(__file__).parents[2] / "data" / "synthetic"
FIXTURES = load_fixtures(DATA_DIR)


def extract(case_id: str, kind: str):
    upload = Upload(
        id=f"{case_id}-{kind}",
        claim_id=case_id,
        kind="image",
        filename=f"{kind}.png",
        path=str(DATA_DIR / case_id / f"{kind}.png"),
    )
    client = StubProvider(Role.VISION, FIXTURES)
    return extract_document(DocumentInput(upload=upload, case_id=case_id, kind=kind), client)


def values(result) -> dict[str, str]:
    return {field.name: field.value for field in result.fields}


def test_clean_form_yields_cited_fields() -> None:
    result = extract("C01", "claim_form")

    assert values(result)["patient_ref"] == "PT-001"
    assert values(result)["admission_date"] == "2026-10-12"
    assert result.retake_reasons == []
    assert all(field.citations for field in result.fields)


def test_every_citation_points_at_the_upload_region() -> None:
    result = extract("C01", "claim_form")

    for field in result.fields:
        citation = field.citations[0]
        assert citation.kind == "image"
        assert citation.source_id == "C01-claim_form"
        assert len(citation.region) == 4


def test_signature_is_reported_present_or_absent() -> None:
    assert values(extract("C01", "claim_form"))["clinician_signature"] == "present"
    assert values(extract("F01", "claim_form"))["clinician_signature"] == "absent"


def test_non_itemised_invoice_is_detected() -> None:
    assert values(extract("C01", "invoice"))["invoice_itemised"] == "yes"
    assert values(extract("F02", "invoice"))["invoice_itemised"] == "no"


def test_blurred_form_requests_a_retake_instead_of_guessing() -> None:
    result = extract("F08", "claim_form")

    assert result.retake_reasons
    assert "patient_ref" not in values(result) or "admission_date" not in values(result)


@pytest.mark.parametrize("case_id", ["C01", "F01", "F02", "F03", "F04", "F05"])
def test_demo_cases_extract_practitioner(case_id: str) -> None:
    assert values(extract(case_id, "claim_form"))["practitioner_id"].startswith("PR-")


class Canned:
    def __init__(self, content: str) -> None:
        self.content = content

    def complete(self, request):
        from app.models import ChatResponse

        return ChatResponse(content=self.content, model_id="canned", provider="canned")


def canned(kind: str, content: str):
    upload = Upload(
        id="X-doc",
        claim_id="X",
        kind="image",
        filename=f"{kind}.png",
        path=str(DATA_DIR / "C01" / f"{kind}.png"),
    )
    return extract_document(DocumentInput(upload=upload, case_id="X", kind=kind), Canned(content))


def test_null_value_is_a_retake_not_the_text_none() -> None:
    result = canned(
        "claim_form",
        '{"fields":[{"name":"practitioner_id","value":null,"confidence":null}],'
        '"signature_present":true,"unreadable":[]}',
    )

    assert "practitioner_id" not in values(result)
    assert any("practitioner_id" in reason for reason in result.retake_reasons)


def test_malformed_output_becomes_a_retake_request() -> None:
    result = canned("claim_form", "I could not read this page.")

    assert result.fields == []
    assert result.retake_reasons


def test_invoice_amount_with_separators_is_read() -> None:
    result = canned(
        "invoice",
        '{"lines":[{"description":"Consultation","amount":"1,500"},'
        '{"description":null,"amount":700}],"total":{"amount":"2,200"},"itemised":true}',
    )

    assert values(result)["invoice_total"] == "2200"
