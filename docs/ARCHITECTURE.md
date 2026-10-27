# Lipwad — Architecture (Hackathon v1)

**Stack:** Python 3.12 + FastAPI (backend, agent) · React + Vite + TypeScript, installable PWA via `vite-plugin-pwa`, design tokens as CSS variables from `design/tokens.css` (frontend) · SQLite via SQLAlchemy (swap to Postgres later through `DATABASE_URL`) · local file storage for uploads.

## 1. The agent loop
```
upload (photos + voice) 
  → INTAKE      segment (SAM 3.1) · extract (Muse Spark vision) · transcribe (Muse Voice Transcribe)
  → CODING      map text to HIE terminology codes (fine-tuned Muse open model on Fireworks)
  → RULES       agentic retrieval over SHA corpus, filtered by date of service, facility level, package
  → VERIFY      every field must carry a citation; cross-document consistency checks
  → STATUS      green / amber / red with specific reasons
  → HUMAN       clerk/clinician reviews, fixes, confirms
  → SUBMIT      HIE Claims API (sandbox or mock)
  → RESCUE      on return/rejection: retrieve cited rule, compare with evidence, draft fix, countdown
```
The orchestrator is a single agent with typed tools. It loops (re-reads a region, re-queries a rule, asks the user for a missing document) until the claim reaches a terminal status or needs human input.

## 2. Model roles
| Role | Model | Where |
|---|---|---|
| Reasoning loop, rules judgement | Muse Spark Open (`meta-models/muse-spark-open-1026`) | Baseten |
| Fast triage, first-pass extraction, batch | Muse Glimmer | Modal Endpoints |
| Terminology coding specialist | Fine-tuned Muse open model | Fireworks |
| Segmentation | SAM 3.1 | Meta Model API |
| Vision extraction | Muse Spark | Meta Model API |
| Speech to text | Muse Voice Transcribe | Meta Model API |

All model calls go through one `models/` client layer with a provider switch, so any role can fall back to the Meta Model API if a partner credit doesn't come through.

## 3. Citation data model (the core)
Every extracted or derived value is a `Field`:
```python
class Citation(BaseModel):
    kind: Literal["image", "audio", "rule"]
    source_id: str            # upload ID or rule ID
    region: list[list[float]] | None = None   # SAM mask polygon or bbox, normalised 0–1 (image)
    page: int | None = None
    t_start: float | None = None   # seconds (audio)
    t_end: float | None = None
    rule_version: str | None = None  # e.g. "2026-07" (rule)
    quote: str | None = None   # short extracted text/transcript snippet

class Field(BaseModel):
    name: str                 # e.g. "admission_date"
    value: str
    confidence: float
    citations: list[Citation] # empty → flagged, blocks green
    confirmed_by: str | None = None
```
A `Claim` holds fields, coded lines (each a `Field`), flags, status, HIE IDs, and the deadline timestamps (submission: 7 days from discharge; resubmission: 14 days from return).

## 4. Tools (typed contracts — wrapped as MCP later)
**Intake:** `segment_document(upload_id)`, `extract_fields(upload_id, region)`, `transcribe(upload_id)`
**Coding:** `code_terms(text, context)`, `lookup_terminology(query)`
**Rules:** `search_rules(query, date_of_service, facility_level, package)`, `get_rule(rule_id, version)`
**HIE:** `check_eligibility(patient_ref)`, `lookup_practitioner(id)`, `lookup_facility(id)`, `submit_claim(claim)`, `get_claim_status(hie_id)`, `edit_claim(hie_id, patch)`
**User:** `request_document(claim_id, what, why)`

Each tool: Pydantic input/output, no side effects outside its scope, every result returns citations where applicable. Planned MCP grouping: `hie-mcp` (HIE + terminology) and `sha-rules-mcp` (rules).

## 5. Rules corpus and retrieval
Source documents are listed with version and effective dates in `SOURCES.md`. They are chunked by rule or clause, and each chunk stores `rule_id`, `version`, `effective_from`, `effective_to`, `facility_levels` and `packages`. Retrieval combines a metadata filter (date of service, facility level, package) with hybrid search (BM25 plus embeddings). The agent may issue several retrievals per claim, and every rule it uses is attached as a citation.

## 6. HIE adapter
`hie/` has two implementations behind one interface: `SandboxHIE`, which uses OAuth credentials from env against the DHA sandbox, and `MockHIE`, which returns identical FHIR-shaped responses with scripted outcomes (accept, return, reject with reason) for the demo cases. `HIE_MODE=mock|sandbox` selects between them.

## 7. Repo layout
```
lipwad/
  AGENTS.md
  docs/        BRIEF.md PRD.md ARCHITECTURE.md DATA.md SOURCES.md
  backend/     app/ (api, agent, tools, models, hie, rules, db) · tests/
  frontend/    src/ (screens, components, api)
  data/        synthetic/ (claims, photos, audio) · corpus/ (SHA docs)
  mcp/         hie_mcp/ · sha_rules_mcp/   (stretch)
```

## 8. Testing
The seeded failure cases in `DATA.md` are the test suite. Each case has an expected status and reason, and CI-style `pytest` runs them end to end against `MockHIE`.
