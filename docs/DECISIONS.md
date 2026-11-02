# Lipwad — Decisions

Choices that resolve gaps or conflicts in the spec. Change one here before changing the behaviour.

| Topic | Decision | Reason |
|---|---|---|
| SHA rules | Placeholder rules marked `v[PLACEHOLDER]` until `SOURCES.md` is filled. Tests assert reason codes, not rule text. | Rule text may only come from registered sources. |
| Test data | Each case has `ground_truth.json` and fixture model responses, so the suite runs without media or network. | Tests must be deterministic and free. |
| F05 colour | The claim stays amber; its countdown chip turns red under 48 hours. | `DATA.md` expects amber, and the design reserves red for imminent deadlines. |
| Claim state | Lifecycle (draft, submitted, returned, rejected, paid) is stored separately from readiness (green, amber, red). | F09 is a lifecycle state, not a colour. |
| Offline capture | Out of scope for v1. | The PRD excludes offline mode; this overrides `DESIGN_PROMPT.md`. |
| Terminology | Placeholder codes behind `lookup_terminology` until the HIE code system is confirmed. | `TERM-01` in `SOURCES.md` is blank. |
| Retrieval | Keyword ranking uses SQLite FTS5. Embeddings go through the model client layer. | Hybrid search without a new search dependency. |
| Reason messages | A static catalogue of reason codes with English and Kiswahili text. | Reason text must be predictable and reviewable. |
| Access | One demo user, no authentication. | Multi-user accounts are out of scope. |
| Tooling | `uv` for Python, `npm` for the frontend, Vitest for frontend tests. | One tool per job. |
| Git | Feature branches, reviewed PRs, merge commits, no squash. | Commit history is the originality evidence. |
| Scope | C01 and F01–F05 first, then F06 and F07. Today, Claim review and one rescue come before Capture and Money. | Prioritises the demo in the remaining build window. |
