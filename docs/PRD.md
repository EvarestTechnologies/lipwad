# Lipwad — Product Requirements Document (Hackathon v1)

**Owner:** Stella Achar Oiro, Evarest Technologies · **Build window:** Oct 27 – Nov 4, 2026 · **Track:** Startup

## 1. Purpose
Lipwad gets Kenyan hospitals paid. It turns scattered claim evidence (paper forms, phone photos, lab slips, staff voice notes) into complete, coded, source-cited SHA claims, checks them against the rules that apply, submits through the national HIE, and repairs rejections before the 14-day resubmission window closes. See `BRIEF.md` for the problem summary.

## 2. Users
**Claims clerk (primary).** Assembles and submits claims. Works on a shared desktop and a phone, under time pressure. Speaks English and Swahili, often mixed. Needs to know exactly what is missing and fix it fast.

**Clinician.** Treats the patient and signs documentation. Has seconds, not minutes. Needs to dictate, review and sign without typing.

**Medical superintendent / facility owner (buyer).** Cares about cash flow and audit exposure. Needs to see money submitted, at risk, recovered and pending.

## 3. Core user stories
1. As a clerk, I photograph a patient's claim documents and record a voice note, and Lipwad builds a draft claim from them.
2. As a clerk, I see each claim as green (ready), amber (one specific fix) or red (blocked, with a plain-language reason).
3. As a clerk, I click any field and see exactly where it came from: the highlighted region of the photo, the audio moment, or the SHA rule and version.
4. As a clerk, I am told precisely what is missing ("itemised invoice", "signature on page 2") and can snap it to resolve the flag.
5. As a clinician, I review the draft summary and coded lines, correct anything, and confirm. Nothing is submitted without human confirmation.
6. As a clerk, I submit a confirmed claim to the HIE and track its status.
7. As a clerk, when a claim is returned or rejected, Lipwad explains why, proposes the fix with evidence, and shows a countdown to the resubmission deadline.
8. As a superintendent, I see shillings submitted, at risk, rescued and pending, by week.
9. As a clerk, I open Lipwad to a Today list of what needs me, with one button per task, and a feed of what Lipwad already handled.

## 4. Functional requirements

**Intake**
- Accept images (JPG/PNG/PDF pages) and audio (voice notes up to 3 minutes).
- Segment documents and regions in photos (SAM 3.1). Extract fields with Muse Spark vision.
- Transcribe English, Swahili and Sheng audio (Muse Voice Transcribe).

**Coding**
- Map extracted diagnoses, procedures and services to the coded terminology the HIE requires.
- Keep the source citation on every coded line.

**Rules check (agentic retrieval)**
- Determine the applicable benefit package, facility level, tariff and required documents for the claim's date of service.
- Retrieve only the rule versions in force on that date. Re-query when evidence conflicts.
- Produce a per-claim status (green, amber, red) with specific, actionable reasons.

**Verification**
- Every claim field must cite a source: image ID plus region, audio ID plus timestamp, or rule ID plus version. Uncited fields are flagged and block green status.
- Flag inconsistencies between documents (dates, names, outpatient vs inpatient).

**Submission and rescue**
- Check eligibility and submit, track and edit claims via the HIE Claims API (sandbox). Use a mock adapter with identical shapes if the sandbox is unavailable.
- On return or rejection, retrieve the cited rule, compare it with the evidence, draft the corrected claim, and show the deadline countdown.

**Today (home)**
- A to-do list, not a dashboard: money at risk today, "Needs you" tasks (each with exactly one primary fix action), and a "Lipwad is working" activity feed with timestamps and citation chips.
- Returned and rejected claims appear here as rescue tasks with their countdown. There is no separate Rescue section.

**Money**
- One page: submitted, at risk, rescued and pending totals, one weekly "rescued" bar chart, and a "closing soon" list, all from local claim data.

**Navigation**
- Four destinations only: Today, Claims, Money, SHA rules, plus a global New claim action. Desktop uses a navy sidebar; mobile uses an installable PWA with a bottom tab bar and a centre camera button. See `DESIGN_PROMPT.md` and `design/`.

**No chatbot.** Lipwad communicates through tasks, the activity feed and the claim-scoped ask box below.

**Stretch: Ask about this claim (after all acceptance criteria pass)**
- A question box on Claim review that answers only from that claim's evidence and the SHA rules corpus, cites every statement, and refuses clinical questions.

**Stretch: MCP servers (target Nov 2, only if all acceptance criteria pass)**
- Build every agent tool as a typed function with a clear input/output contract from day one, so wrapping is mechanical.
- `hie-mcp`: eligibility check, claim submit / status / edit, practitioner and facility registry lookups, terminology lookup. Calls the HIE sandbox or the mock adapter.
- `sha-rules-mcp`: search rules by date of service, facility level and benefit package; get a rule by ID and version. Every result carries its citation.
- Purpose: auditable tool boundaries for the agent, and a standard interface any certified HMIS or external agent can call. This is the "HMIS vendors plug into Lipwad" story.

## 5. Non-functional requirements
- **Human in the loop:** No claim is submitted without explicit confirmation.
- **No clinical advice:** Lipwad documents and codes what happened. It never recommends treatment, and it never adds or upgrades services.
- **Data:** Synthetic data only. No real patient records. Credentials live only in environment variables.
- **Speed:** A draft claim is ready within 60 seconds of upload for a typical file.
- **Language:** The interface is in English, and reason messages can be shown in Swahili.
- **Open source:** Public repo under Apache 2.0. Everything was built during the hackathon window.

## 6. Out of scope (v1)
Production HMIS integration, real patient data, offline mode, payment guarantees, private insurers and multi-facility accounts.

## 7. Acceptance criteria (demo-critical)
- Five seeded failure cases are each caught before submission with the correct reason: missing signature, non-itemised invoice, outpatient billed as inpatient, a practitioner not found in the registry, and a resubmission on day 13 of 14.
- A clean claim goes from photos plus voice note to green in under two minutes of clerk time.
- Clicking any field shows its source in under one second.
- One rejected claim is repaired and resubmitted through the sandbox or the mock adapter.
- Today and Money reflect all demo claims, and resolving a task updates the at-risk total.
- The PWA installs on Android and the capture flow works at 360 px width.

## 8. Risks
- **HIE sandbox access or terms:** Mitigated by the mock adapter with identical shapes.
- **Poor photo or audio quality:** Mitigated by asking for a retake rather than guessing.
- **Perceived as medical AI:** Mitigated by the explicit no-advice guardrail, stated in the UI and the demo video.
- **Rules corpus gaps or versions:** Mitigated by SOURCES.md listing each document's version and date.
