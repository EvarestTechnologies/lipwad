# Lipwad — Synthetic Data Spec

**Rule: no real patient data, ever.** Every patient, practitioner ID, facility and document here is invented. Real-world forms are used only as blank templates.

## 1. What we generate
For each claim case:
- **Documents:** blank SHA-relevant forms filled with invented details, then printed and photographed on a phone. Some are clean, some crumpled, angled, badly lit or partly shadowed.
- **Invoice:** itemised or deliberately non-itemised, as the case requires.
- **Supporting slips:** lab or imaging slips where relevant.
- **Voice note (30–90 s):** a clerk or clinician describing the case in mixed English, Swahili and Sheng, recorded by the team.
- **Ground truth JSON:** expected fields, codes, status and reasons.

Stored under `data/synthetic/<case_id>/` with `ground_truth.json`.

## 2. Case set (minimum 12)
| ID | Scenario | Facility | Expected | Reason |
|---|---|---|---|---|
| C01 | Clean outpatient visit | Level 3 | Green | — |
| C02 | Clean inpatient admission, full docs | Level 4 | Green | — |
| C03 | Clean maternity (normal delivery) | Level 4 | Green | — |
| F01 | Discharge summary unsigned | Level 4 | Amber | Missing clinician signature (page/region cited) |
| F02 | Invoice not itemised | Level 4 | Amber | Itemised invoice required |
| F03 | Outpatient visit billed as inpatient | Level 3 | Red | Service type inconsistent with documents |
| F04 | Practitioner not found in registry | Level 4 | Red | Practitioner validation failed |
| F05 | Returned claim, day 13 of 14 | Level 4 | Amber + countdown | Rescue flow, one day left |
| F06 | Dates disagree across documents | Level 3 | Amber | Admission date mismatch (both sources cited) |
| F07 | Service outside facility level | Level 2 | Red | Not covered at this facility level |
| F08 | Blurry photo, key field unreadable | Level 3 | Amber | Retake requested, no guessing |
| F09 | Rejected claim with stated reason | Level 4 | Rescue | Fix drafted with rule cited |

Add more as time allows. C01–C03 and F01–F05 are demo-critical.

## 3. Ground truth format
```json
{
  "case_id": "F02",
  "facility_level": 4,
  "date_of_service": "2026-10-12",
  "expected_status": "amber",
  "expected_reasons": ["itemised_invoice_missing"],
  "fields": {"patient_name": "…", "admission_date": "…"},
  "codes": ["…"],
  "mock_hie_outcome": "accept"
}
```

## 4. Production checklist
- [ ] Download blank forms and note them in SOURCES.md
- [ ] Write invented patient and practitioner profiles
- [ ] Fill, print and photograph each case (aim for 2–4 photos per case)
- [ ] Record voice notes and name files `<case_id>_voice.m4a`
- [ ] Write ground_truth.json for each case
