# Lipwad

**Lipwad gets Kenyan hospitals paid.** It reads photographed claim documents, cites every value to the exact place it came from, checks the claim against SHA rules, and repairs returned claims before the 14-day resubmission window closes.

> **Lipwad is not medical AI.** It documents and codes what already happened. It never gives clinical advice, never recommends treatment, and never adds or upgrades services or amounts. Nothing reaches the national HIE without a named person's confirmation.

**Live demo:** https://stellaacharoiro--lipwad-web.us-east.modal.run (all patients, practitioners and facilities are synthetic)

Built solo for the Meta Global AI Developer Hackathon (Startup track), Oct 27 – Nov 4, 2026, by Evarest Technologies. Everything in this repository was written during the build window; the commit history is the record.

## The problem
Kenyan hospitals deliver care under the Social Health Authority (SHA) and then lose the money over paperwork: unsigned forms, invoices without itemised services, service types that don't match the documents, practitioners missing from the registry, and returns that run out the 14-day clock. The evidence usually exists, scattered across paper and phones. SHA screens claims with automation; hospitals have nothing on their side.

## What Lipwad does
1. **Reads the claim file.** Muse Spark vision transcribes each photographed document into fields. Every field carries a citation: the document and the region of the photo it came from. A blurred page produces a retake request, never a guess.
2. **Hears the voice note.** Muse Voice Transcribe transcribes a staff voice note into timed segments. A date that was said becomes a field cited to the seconds it was spoken, and Claim review plays exactly that moment.
3. **Verifies it.** The agent checks the practitioner and facility against the registry, cross-checks what was said against what was written, then runs rule checks. Each finding cites the evidence and the rule it relies on.
4. **Decides and explains.** Claims come out green (ready), amber (one named fix) or red (blocked). Muse Spark Open explains the outcome in English and Kiswahili. The model explains; it never sets the status, so it cannot turn a blocked claim green.
5. **Submits only with a person's OK.** A green claim goes to the HIE after a named clerk confirms they checked every field.
6. **Rescues returned claims.** For a returned claim, Lipwad reads the corrected page, shows exactly which field changed, and resubmits only that correction after confirmation, with the deadline countdown in view.

Clicking any field in Claim review highlights the region of the photo it came from.

## Meta models and where they run
| Role | Model | Served by |
|---|---|---|
| Reading documents, with value regions for click-to-source | Muse Spark 1.3 (vision) | Meta Model API |
| Transcribing voice notes, with timestamps for audio citations | Muse Voice Transcribe 1.0 (realtime) | Meta Model API |
| Reasoning and bilingual explanation in the agent loop | Muse Spark Open (`meta-models/muse-spark-open-1026`) | Baseten |
| Development: model client layer (#7) | Muse Code | Local terminal |

All model calls go through one client layer (`backend/app/models/`) that resolves each role to a provider, so any role can fall back to the Meta Model API.

## Results on the synthetic case set
Running the agent live on real models, every demo case reaches its expected status and reason:

| Case | Scenario | Result |
|---|---|---|
| C01–C03 | Clean outpatient, inpatient and maternity claims | Green |
| F01 | Claim form unsigned | Amber · signature missing |
| F02 | Invoice not itemised | Amber · itemised invoice missing |
| F03 | Outpatient visit billed with inpatient bed days | Red · service type inconsistent |
| F04 | Practitioner not in registry | Red · practitioner not found |
| F05 | Returned claim on day 13 of 14 | Amber · deadline near; rescue resubmits the signed page |
| F06 | Voice note gives a different admission date from the form | Amber · admission date mismatch, both sources cited |
| F07 | Inpatient care billed at a level 2 facility | Red · outside facility level |
| F08 | Blurred photo | Amber · retake requested, nothing guessed |
| F09 | Rejected claim | Amber · claim rejected |

A claim takes 22–37 seconds from photos to a cited status. The same cases run in CI through recorded model responses, so tests never call a paid model.

## Architecture
```
photos ─▶ Muse Spark vision ─────┐
voice  ─▶ Muse Voice Transcribe ─┴─▶ cited fields ─▶ registry + cross-source + rule checks ─▶ status
                                                                                   │
                                                 Muse Spark Open ◀─────────────────┘ explanation (EN/SW)
                                                         │
                                 named confirmation ─▶ HIE adapter (mock) ─▶ rescue loop
```
- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy and SQLite. Every agent tool is a typed function with Pydantic input and output.
- **Frontend:** React, Vite and TypeScript as an installable PWA, styled only from `design/tokens.css`.
- **HIE:** `MockHIE` returns FHIR-shaped responses with scripted outcomes. It stands in for the DHA sandbox, which was not available.
- **Hosting:** Modal, with SQLite and HIE state on a Volume.

Details are in `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` and `docs/DEPLOY.md`.

## Run it
```bash
cp .env.example .env        # add META_MODEL_API_KEY and BASETEN_API_KEY
make seed                   # load the synthetic cases
make dev                    # backend on :8000, frontend on :5173
make test                   # 224 backend tests, no network
make deploy                 # build and deploy to Modal
```

## Limitations
- **Rules are placeholders.** Rule IDs are cited with version `v[PLACEHOLDER]` until the SHA source documents are registered in `docs/SOURCES.md`. Lipwad never invents rule text.
- **Mock HIE.** Submission and resubmission go to `MockHIE`, not the DHA sandbox.
- **Voice notes are English only.** Kiswahili is not yet in Muse Voice Transcribe's language list.
- **Not yet built:** SAM 3.1 segmentation, the Capture screen, rules retrieval over a registered SHA corpus, and terminology coding. Codes are placeholders.
- **Synthetic data only.** All documents are generated from ground truth by `backend/scripts/make_documents.py` and marked as synthetic.

## Credits
- Fonts: Schibsted Grotesk and Martian Mono, via Google Fonts under the SIL Open Font License.
- Open-source libraries listed in `backend/pyproject.toml` and `frontend/package.json`.

Licensed under Apache 2.0.
