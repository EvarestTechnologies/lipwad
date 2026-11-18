# Lipwad — Sources

Every document in the rules corpus and every blank template must be listed here before use. The agent cites rules by `rule_id` and `version`, so this file is the backbone of verifiability. Only use documents that are publicly published or that we have the rights to.

## Rules corpus
Every rule Lipwad cites is listed here and in `backend/app/agent/rules.py`, which serves the same text on the Rules screen. Quotes are copied word for word; "..." marks words left out. Status: **final** (final as published or gazetted), **news** (context only, never cited alone) or **lipwad** (Lipwad's own evidence check, not an SHA rule). Checked against each source on 18 Nov 2026.

| Rule ID | Source | Issuer | Version | Status | Clause and page | URL | Exact quote |
|---|---|---|---|---|---|---|---|
| SHA-A-13.2.1-SUBMIT-7D | Contract for the Provision of Healthcare Services, Part A, Master General Terms and Conditions | Social Health Authority | 16 Oct 2026 | final | 13.2.1, p. 52 | https://www.sha.go.ke/wp-content/uploads/2026/10/PART-A-Master-General-Terms-and-Conditions_1.pdf | "The Healthcare Provider shall submit all its Claims electronically to the Authority or its appointed agent within seven (7) days of the date of Service or of the date of discharge of the Beneficiary, whichever is later." |
| SHA-A-13.1.2-ACCURATE | Part A, as above | Social Health Authority | 16 Oct 2026 | final | 13.1.2, p. 52 | as above | "The Healthcare Provider certifies that all data submitted in relation to a Beneficiary shall at all times be accurate, complete and truthful." |
| SHA-A-13.3.1-SUPPORTING-DOCS | Part A, as above | Social Health Authority | 16 Oct 2026 | final | 13.3.1, p. 53 | as above | "Each Claim shall be supported by the documentation prescribed by the Authority for the relevant Fund and service line, including the beneficiary verification reference, the pre-authorisation reference where applicable, the discharge summary, the Care Plan, the medical report, the itemised invoice coded to the Tariff, the treatment sheet and medication chart, investigation requests and results, operation notes where a procedure was performed, and referral documents where applicable." |
| SHA-A-13.4.3-LICENSED | Part A, as above | Social Health Authority | 16 Oct 2026 | final | 13.4.3, pp. 53-54 | as above | "The Healthcare Provider shall not submit a Claim which involves ... a Service delivered by a person not licensed or authorised to deliver it" |
| SHA-A-13.5.2-RESUBMIT-14D | Part A, as above | Social Health Authority | 16 Oct 2026 | final | 13.5.2, p. 54 | as above | "The Healthcare Provider shall correct and resubmit a Sent Back Claim within fourteen (14) days of the date on which it was returned. A Sent Back Claim which is not resubmitted within that period shall lapse and shall not be payable." |
| SHA-A-13.8.1-REVIEW-7WD | Part A, as above | Social Health Authority | 16 Oct 2026 | final | 13.8.1, p. 55 | as above | "A Healthcare Provider aggrieved by the rejection or reduction of a Claim may, with new evidence, request a review by the Authority within seven (7) Working Days of notification." |
| SHA-B2-SHIF-DOCS | Contract for the Provision of Healthcare Services, Part B2, Social Health Insurance Fund Contract | Social Health Authority | 16 Oct 2026 | final | 8.1.2, p. 11 | https://www.sha.go.ke/wp-content/uploads/2026/10/PART-B2-Social-Health-Insurance-Fund-Contract-1.pdf | "... the itemised invoice coded to the Tariff, and the discharge summary signed by the treating Healthcare Professional." |
| SHI-REG-58-LODGE-7D | The Social Health Insurance Regulations, 2024, Legal Notice 49 of 2024 (Kenya Gazette Supplement No. 60, 8 Mar 2024) | Cabinet Secretary for Health | LN 49 of 2024 | final | reg. 58(1) | https://new.kenyalaw.org/akn/ke/act/ln/2024/49/eng@2025-02-28 | "A healthcare provider or health facility shall, within seven days from the date of discharge of the patient, lodge a claim to the Claims Management Office or a medical insurance provider and claim settling agent, where applicable, for review and processing of the claim." |
| SHI-FORM3-FIELDS | LN 49 of 2024, as above | Cabinet Secretary for Health | LN 49 of 2024 | final | First Schedule, Form 3 | as above | "All fields in this form are mandatory. Incomplete forms will not be processed." |
| SHI-SCHED-INPATIENT-LEVEL | LN 49 of 2024, as above | Cabinet Secretary for Health | LN 49 of 2024 | final | Second and Third Schedules | as above | Primary Healthcare Fund inpatient point of access "Level 2-4". Social Health Insurance Fund inpatient point of access "Level 4 - 6". Registered for Phase 2; nothing is flagged against it yet. |
| DHA-HIE-REQUIRED-DOCS | Understanding Virtual Claims | Digital Health Agency, HIE documentation | last modified 28 Sep 2026 | final | Provider Claim field reference, note | https://hie-docs.dha.go.ke/docs/claims/guides/understandingClaims | "If any required document is missing, the claim submission will be blocked." |
| SHA-NEWS-3-DOCS | SHA halts Ksh3B claims and issues 14-day ultimatum | People Daily (Kenneth Mwenda) | 15 Sep 2025 | news | news report | https://peopledaily.digital/news/sha-halts-ksh3b-claims-and-issues-14-day-ultimatum | "According to SHA, every claim must include three mandatory documents: a duly filled claim form, an itemised invoice, and a discharge or case summary." |
| LIPWAD-EVIDENCE-QUALITY | Lipwad evidence check | Lipwad | | lipwad | | | Lipwad does not read a value it cannot see or hear clearly; a person retakes the photo, records the note again or reviews it. Not an SHA rule. |
| LIPWAD-CODING-PENDING | Lipwad coding status | Lipwad | | lipwad | | | Lipwad assigns no service or diagnosis codes until SHA's coding standard is confirmed (Phase 2). Not an SHA rule. |

Notes on these sources:
- The Part A text was read from the page images: the PDF is a scan with no text layer.
- LN 49 was read from a copy of the gazette supplement (https://www.ramco.com/hubfs/SHI%20REGULATIONS%202024.pdf.pdf) because Kenya Law did not load. LN 55 of 2025 later amended reg. 59(1)(a); it did not change reg. 58, Form 3 or the Schedules.
- The People Daily quote was read by a research assistant in a browser; the site blocks automated reading, so Lipwad treats it as news context only.

### Superseded, do not cite
| Document | Why |
|---|---|
| MoH "Social Health Insurance (General) Regulations, 2024", Nov 2024 copy with a blank legal notice number | A consultation draft. Use LN 49 of 2024. |
| SHA Part B3 ECCIF contract, Sep 2026 (`/2026/09/04-PART-B3-...`) | A DRAFT for consultation, replaced by the contract set published in Oct 2026. |
| News reports of the 14-day resubmission window (Kenyans.co.ke and People Daily, Sep 2025) | No longer the source for the 14-day rule. Use SHA-A-13.5.2-RESUBMIT-14D. |

Capture superseded versions when a rule changes, with effective-from and effective-to dates, so claims are judged by the rule in force on the date of service.

## Integration documentation
| Doc ID | Title | Issuer | URL | Date accessed |
|---|---|---|---|---|
| DHA-HIE-01 | HIE Claims API docs, including the claim attachment `document_type` list | Digital Health Agency | https://hie-docs.dha.go.ke | 18 Nov 2026 |
| DHA-HIE-02 | HMIS–HIE integration guide | Digital Health Agency | https://afyalink.dha.go.ke/hmis-sha-integration-guide | |

## Blank form templates
None used. The synthetic documents use invented layouts and do not copy any official SHA form.

## Terminology
None registered. SHA's coding standard (ICD-10 or ICD-11) is not confirmed, so Lipwad assigns no codes and shows every service as "not coded" (see LIPWAD-CODING-PENDING).

## Problem data (cited in the pitch slides, video and submission)
| ID | Title | Publisher | URL | Date | Used for | Terms |
|---|---|---|---|---|---|---|
| NEWS-01 | SHA report: Missing documents cause most claim rejections | The Star (Kenya) | https://www.the-star.co.ke/news/2026-02-13-sha-report-missing-documents-cause-most-claim-rejections | 13 Feb 2026 | 91,935 claims rejected for missing or incomplete documents; 23,000 for late resubmission (SHA report, Oct 2024 to Jan 2026) | Figures cited with attribution; no article text reproduced |
| NEWS-02 | SHA rejects one in five claims from hospitals | The Star (Kenya) | https://www.the-star.co.ke/news/2026-07-04-sha-rejects-one-in-five-claims-from-hospitals | 4 Jul 2026 | About 1 in 5 county hospital claims unpaid; over KSh 8B of KSh 40.91B returned, awaiting documents or rejected (SHA statement, data to 30 Jun 2026) | Figures cited with attribution; no article text reproduced |

These are news reports of SHA's own figures, not SHA rule documents, so they are never cited as rules.

## Synthetic media
| Asset | How it was made | Rights and notes |
|---|---|---|
| `data/synthetic/*/claim_form*.png`, `invoice.png`, `discharge_summary.png`, `case_summary.png` | Rendered from each case's `ground_truth.json` by `backend/scripts/make_documents.py` | Original work, watermarked "SYNTHETIC - DEMO ONLY". Names, facilities and practitioners are invented. |
| `data/synthetic/F06/voice_note.wav` | Spoken by the macOS system voice "Tessa" from an original, invented script | Apple's licence allows system-voice output in personal, non-commercial projects; replace it with a team recording before any commercial use. |

## Fonts and libraries
| Asset | Source | Licence |
|---|---|---|
| Schibsted Grotesk, Martian Mono | Google Fonts | SIL Open Font License 1.1 |
| Python and npm packages | `backend/pyproject.toml`, `frontend/package.json` | Each package's own open-source licence |

