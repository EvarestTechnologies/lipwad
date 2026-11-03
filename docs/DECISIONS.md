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
| Voice notes | Muse Voice Transcribe is called through the Meta Model API's realtime WebSocket (`wss://api.meta.ai/v1/asr/realtime`), streaming 80 ms PCM16 frames at real-time pace. Segments are timed from the server's `audioProcessedMs`. | The API offers no file-transcription endpoint. Streaming a 20-second note takes about 20 seconds. |
| Voice languages | Voice notes are transcribed with an English language bias. Kiswahili and Sheng notes are not supported yet. | Kiswahili is not in Muse Voice Transcribe's published language list. |
| Spoken dates | The listen tool reads a calendar date from the transcript with a deterministic parser, and cites the segment it came from. | A wrong date would raise a false flag; parsing what was actually said is verifiable. |
| SAM 3.1 | Not used for click-to-source. Muse Spark's value boxes remain the highlight. | Tested on the claim forms through the Responses API: SAM 3.1 found the ruled lines but returned nothing for "text" or "signature", so it cannot outline the values a clerk clicks. |
| Public demo guards | The live demo has no login. Paid agent runs are capped per UTC day (`LIPWAD_DAILY_RUNS`, 30 on Modal), one request works on a claim at a time, and the demo restores itself every `LIPWAD_DEMO_RESET_HOURS` (6 on Modal). | Judges and voters share one demo until Nov 16; the guards keep it working and keep spend bounded without adding accounts. |
| Demo restore | `make snapshot` saves the reviewed demo; a restore copies it back and moves every stored time forward by the time since the snapshot, so F05 stays on day 13 of 14. With no snapshot, a restore reseeds the cases. | A plain reseed would leave Today empty and spend the run budget re-reviewing. |
| Corrected pages on drafts | A draft with a corrected page on file (F01) can read it, fixing only the fields that changed, and is then submitted normally. Resubmission stays limited to returned or rejected claims. | Makes "snap the signed page" completable before Capture exists, without letting a draft skip submission. |

