from app.agent.documents import BASELINE, Requirement, missing, present_types, required_documents


def test_baseline_names_the_three_documents_every_claim_needs() -> None:
    assert [r.any_of for r in BASELINE] == [
        ("CLAIM_FORM",),
        ("INVOICE", "FINAL_BILL"),
        ("DISCHARGE_SUMMARY", "CASE_SUMMARY"),
    ]


def test_a_final_bill_satisfies_the_invoice_requirement() -> None:
    assert missing({"CLAIM_FORM", "FINAL_BILL", "CASE_SUMMARY"}, required_documents()) == []


def test_missing_documents_are_named() -> None:
    gaps = missing({"CLAIM_FORM", "INVOICE"}, required_documents())

    assert [r.label for r in gaps] == ["discharge or case summary"]
    assert gaps[0].code == "discharge_summary_missing"


def test_interventions_replace_the_baseline_with_the_union_of_their_requirements() -> None:
    needs = required_documents([["CLAIM_FORM", "LAB_RESULTS"], ["CLAIM_FORM", "THEATRE_NOTES"]])

    assert [r.any_of for r in needs] == [("CLAIM_FORM",), ("LAB_RESULTS",), ("THEATRE_NOTES",)]
    assert isinstance(needs[0], Requirement)


def test_uploaded_files_map_to_hie_document_types() -> None:
    files = ["claim_form.png", "invoice.png", "voice_note.wav", "claim_form_signed.png"]

    assert present_types(files) == {"CLAIM_FORM", "INVOICE"}


def test_a_missing_claim_form_cites_regulation_58_not_the_contract_list() -> None:
    assert BASELINE[0].rule_id == "SHI-REG-58-FORM3"
    assert {r.rule_id for r in BASELINE[1:]} == {"SHA-A-13.3.1-SUPPORTING-DOCS"}
