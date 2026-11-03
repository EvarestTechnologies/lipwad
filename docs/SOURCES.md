# Lipwad — Sources

Every document in the rules corpus and every blank template must be listed here before use. The agent cites rules by `rule_id` and `version`, so this file is the backbone of verifiability. Only use documents that are publicly published or that we have the rights to.

## Rules corpus
| Doc ID | Title | Issuer | Version / effective date | Where obtained (URL) | Date downloaded | Notes |
|---|---|---|---|---|---|---|
| SHA-REG-01 | | | | | | |
| SHA-BEN-01 | Benefit package | | | | | |
| SHA-TAR-01 | Tariffs | | | | | |
| SHA-CIR-01 | Circulars / notices on claims | | | | | |

Capture superseded versions too when a rule changed, with effective-from and effective-to dates, so claims are judged by the rule in force on the date of service.

## Integration documentation
| Doc ID | Title | Issuer | URL | Date accessed |
|---|---|---|---|---|
| DHA-HIE-01 | HIE Claims API docs | Digital Health Agency | https://hie-docs.dha.go.ke | |
| DHA-HIE-02 | HMIS–HIE integration guide | Digital Health Agency | https://afyalink.dha.go.ke/hmis-sha-integration-guide | |

## Blank form templates
| Template ID | Form | Issuer | Where obtained | Notes |
|---|---|---|---|---|
| FORM-01 | | | | |

## Terminology
| ID | Code system | Source | Version | Notes |
|---|---|---|---|---|
| TERM-01 | | | | |

## Synthetic media
| Asset | How it was made | Rights and notes |
|---|---|---|
| `data/synthetic/*/claim_form*.png`, `invoice.png` | Rendered from each case's `ground_truth.json` by `backend/scripts/make_documents.py` | Original work, watermarked "SYNTHETIC - DEMO ONLY". Names, facilities and practitioners are invented. |
| `data/synthetic/F06/voice_note.wav` | Spoken by the macOS system voice "Tessa" from an original, invented script | Apple's licence allows system-voice output in personal, non-commercial projects; replace it with a team recording before any commercial use. |

## Fonts and libraries
| Asset | Source | Licence |
|---|---|---|
| Schibsted Grotesk, Martian Mono | Google Fonts | SIL Open Font License 1.1 |
| Python and npm packages | `backend/pyproject.toml`, `frontend/package.json` | Each package's own open-source licence |

