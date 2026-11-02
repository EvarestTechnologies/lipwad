# AGENTS.md — Lipwad

Lipwad gets Kenyan hospitals paid. It is a multimodal agent that turns photos of paper records and staff voice notes (English, Kiswahili, Sheng) into complete, source-cited SHA claims, checks them against the SHA rules in force on the date of service, submits them through the national HIE, and fixes rejections before the 14-day resubmission window closes. Built for the Meta Global AI Developer Hackathon (build window Oct 27 – Nov 4, 2026; Startup track, solo founder) by Evarest Technologies.

## Read before working
- `docs/BRIEF.md`: problem and solution, half a page
- `docs/PRD.md`: users, stories, requirements, **acceptance criteria** (the definition of done)
- `docs/ARCHITECTURE.md`: agent loop, model roles, **citation data model**, tool contracts, repo layout
- `docs/DATA.md`: synthetic cases C01–C03, F01–F09 (the test suite and the demo script)
- `docs/SOURCES.md`: rules corpus registry (every rule cited by ID and version)
- `docs/DEPLOY.md`: CI/CD pipeline and terminal deployment
- `docs/DECISIONS.md`: choices that resolve gaps in the spec
- `docs/DESIGN_PROMPT.md` and `design/`: UI system, screens and `tokens.css`

## Stack
- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy plus SQLite (`DATABASE_URL`), pytest. Python tooling via `uv`.
- Frontend: React, Vite, TypeScript, `vite-plugin-pwa`. Styles come from `design/tokens.css` variables only.
- Models go through one client layer, `backend/app/models/`, with a provider switch. Every provider speaks the OpenAI-compatible Chat Completions format, so the switch is a base URL, key and model ID per role:
  - Meta Model API (`https://api.meta.ai/v1`): SAM 3.1, Muse Spark vision, Muse Voice Transcribe, and the fallback for every role.
  - Baseten: Muse Spark Open (`meta-models/muse-spark-open-1026`, not the docs' `meta-models/muse-spark-open`) for the reasoning loop.
  - Modal: Muse Glimmer endpoint for triage and batch.
  - Fireworks: coding model (stretch; credits are shortlist-only).
- HIE: `HIE_MODE=mock|sandbox`. Build and test against `MockHIE` first.
- Hosting: Modal (see `docs/DEPLOY.md`).

## Non-negotiable rules
1. **Every field carries a citation** (`Citation`: image plus region, audio plus timestamps, or rule plus version). An uncited field blocks green status. Never drop citations when transforming data.
2. **Human in the loop.** Nothing is submitted to the HIE without explicit user confirmation.
3. **No clinical advice.** Lipwad documents and codes what happened. It never recommends treatment and never adds, upcodes or raises services or amounts. Rescue may only correct a claim toward the evidence.
4. **Synthetic data only.** Never add real patient data. Never invent SHA rule text: use only documents registered in `SOURCES.md`, and leave placeholders where the corpus is missing.
5. **Secrets live in `.env` only.** Never commit keys; keep `.env.example` in sync when adding a variable. The repo is public.
6. **Don't guess on bad input.** An unreadable photo or audio produces a retake request, not an extracted value.
7. **No chatbot UI.** The agent speaks through Today tasks, the activity feed, and (stretch) the claim-scoped "Ask about this claim".
8. **Agent tools are typed functions** with Pydantic input and output and no side effects outside their scope, so they can be wrapped as MCP servers later (`mcp/`, stretch).

## Hackathon rules
These come from the participant guide and decide whether Lipwad is judged at all.
1. **New work only.** Everything in this repo is written during the build window. Never paste in code from other projects. A third-party snippet is allowed only with a compatible licence, and it is credited in the README.
2. **Rights to every asset.** Every outside document, form, font, image or dataset is listed in `docs/SOURCES.md` with its licence or terms before use.
3. **Not medical advice, visibly.** Medical-advice projects are banned outright. The no-advice guardrail appears in the UI near every submit action, in the README's first screen and in the first 20 seconds of the demo video.
4. **Not "basic RAG" or a "simple image analyser".** Both are listed anti-projects. Every feature must show multi-step agent behaviour: the loop re-reads, re-queries, verifies, decides and repairs. Retrieval and extraction are tools inside the loop, never the product.
5. **Real Meta models on the demo path.** Stubs exist for tests and CI only. The demo and the live product call real Meta models. The reasoning loop runs on Muse Spark Open, so the project qualifies for Best Build on Meta Open Weight Models.
6. **Show the Meta tooling.** Meta tooling is 25% of the score. Surface what is distinctive: SAM 3.1 masks as the click-to-source highlight, audio-timestamp citations from Muse Voice Transcribe, and Muse Spark Open's reasoning trace in the activity feed.
7. **Muse Code is part of the toolchain.** Slices built with Muse Code say so in their commit messages, and CI runs a headless `muse exec` check. Only claim Muse Code for work it actually did.
8. **Priorities follow the rubric.** Impact 30%, Meta tooling 25%, demo 25%, technical depth 20%. Demo-critical cases (C01–C03, F01–F05) come before polish; stretch items wait until every PRD acceptance criterion passes.
9. **A live product and a 3-minute video are deliverables.** The live URL is kept up through Nov 16 (community vote). The video has its own script and recording slot. Feature freeze is midday ET on Nov 4; submission is Nov 4, 9 PM ET.
10. **Credit hygiene.** Spend limits are set on every provider. Never loop paid model calls in tests or CI.

## Build order
1. Repo scaffold, CI, `MockHIE`, DB models (`Claim`, `Field`, `Citation`, `Flag`, `Upload`), seeded loader for `data/synthetic/`. A walking skeleton deployed to Modal.
2. Intake: segment, extract, transcribe, all returning cited `Field`s.
3. Rules corpus ingestion with version and effective dates, then metadata-filtered hybrid retrieval.
4. Agent loop: coding, rules check, verify, status, then green/amber/red with reasons. Passing the DATA.md cases is the gate.
5. Submit, status, edit through the HIE adapter; rescue loop with deadline countdowns.
6. Frontend: Today, Claim review (click-to-source), Capture (PWA), Money, matching `design/`.
7. Stretch, only once all PRD acceptance criteria pass: MCP servers, Ask about this claim, Fireworks fine-tune, HIE sandbox mode.

## Commands (create these during scaffold and keep them working)
- `make dev`: backend and frontend together
- `make test`: pytest, including the end-to-end DATA.md cases against `MockHIE`
- `make seed`: load synthetic cases
- `make deploy`: build the frontend and deploy to Modal from the terminal

## Working style
- Small commits with clear messages. Commit history is the hackathon originality evidence, so never squash or rewrite it.
- `make test` is green at every commit, and CI must pass before deploy.
- When a requirement is unclear, check the PRD, then ask. Don't invent scope.
- Ask before adding a dependency outside the stack, changing the data model, or starting any stretch item.
- Update docs when behaviour changes; the README is written in the final days for judges.
