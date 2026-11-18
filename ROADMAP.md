# Lipwad roadmap

Lipwad checks Kenyan hospital SHA claim paperwork before submission. It reads claim photos and staff voice notes, flags gaps, and cites both the evidence (a photo region or a second of audio) and the SHA rule.

## The principle that never changes
- Flag only. Never fill in, guess or change a value.
- A person makes every fix and confirms every claim.
- Never give clinical advice. Never choose or change a diagnosis, code, service or amount.
- Every finding cites a registered rule and its evidence. No finding without both.

## Phases

### 1. Documentation completeness (now)
Catch an incomplete claim before it is submitted, because the appeal starts before the claim is sent.
- Every finding cites a rule registered in `docs/SOURCES.md` with its exact text: SHA Part A and Part B2 (Oct 2026), LN 49 of 2024 and the DHA HIE docs.
- Required documents: claim form, itemised invoice or final bill, and discharge or case summary (Part A 13.3.1). A signed discharge summary for SHIF inpatient claims (Part B2 8.1.2).
- Sent back claims show days left out of 14 (Part A 13.5.2). Rejected claims show the 7 working day review window (Part A 13.8.1).
- An append-only audit trail for every claim, exportable as one file.
- Voice note segments that are not in English go to a person; no value is taken from them.
- Next in this phase: flag a billed service that has no supporting report or clinical notes, and a service line with no charge or no service date.

### 2. Coding and rules (waits for SHA's coding standard)
- Check the service type against the diagnosis code, and the lab and radiology reports each code requires.
- Read required documents from each HIE intervention's `applicableDocumentTypes`; a claim with several interventions needs all of them.
- Fund and facility-level checks. The Primary Healthcare Fund and SHIF both cover inpatient care at Level 4, and no official text yet says whether a claim to the wrong fund is rejected or sent back.

### 3. Appeals
- Help a hospital request a review of a rejected claim within 7 working days, with an evidence pack built from the audit trail.

## Feedback that shaped this plan
| From | What they said | What we build |
|---|---|---|
| A patient safety and QI advisor | The appeal starts before the claim is submitted | Pre-submission checks are the core of the product |
| A patient safety and QI advisor | Flag a service without its supporting report or clinical notes | Phase 1 documentation checks |
| A patient safety and QI advisor | Flag a service with no charge or service date | Phase 1 documentation checks |
| A patient safety and QI advisor | Coding checks: service type against diagnosis code, required lab and radiology reports per code | Phase 2 |
| A patient safety and QI advisor | Hospitals need a way to manage appeals | Phase 3 |
| A systems builder | Records need audit trails | The append-only audit trail |
| Clinicians on X | Transcription must not fail speakers of African languages | The voice note language guard |
| A contact in our network | "Returned is not rejected": hospitals have 14 days to fix a sent back claim | The sent back rescue flow cites Part A 13.5.2 and shows days left |

## Not yet
- Real patient data, shadow mode and redaction wait for registration with the Office of the Data Protection Commissioner, a data protection impact assessment, compliant hosting and a data sharing agreement. Until then Lipwad runs on synthetic data only.
