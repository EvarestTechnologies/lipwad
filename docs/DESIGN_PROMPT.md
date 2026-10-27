# Lipwad — Design Prompt

Paste this into your design tool, or give it to the coding agent when building the frontend. Iterate by changing one section at a time.

---

You are designing **Lipwad**, a web app and installable PWA that helps Kenyan hospitals get paid by SHA (the Social Health Authority). Lipwad turns phone photos of paper records and staff voice notes (English, Kiswahili, Sheng) into complete, cited insurance claims. It checks them against the SHA rules in force on the date of service, submits them, and fixes rejections before the 14-day resubmission window closes.

## Who uses it
- **Claims clerk (primary).** Busy, interrupted, works on a shared desktop and a cheap Android phone. Needs to know what to do next, not to analyse data.
- **Clinician.** Seconds to spare. Dictates, reviews, signs.
- **Facility owner.** Wants one number: how much money is at risk and how much Lipwad saved.

## The core idea for the UI
Lipwad is an agent that works for the hospital, so the interface is a **to-do list run by a colleague**, not a dashboard. The home screen says what needs a person today, how much money is at risk, and what Lipwad already handled. Every task has exactly one primary button that does the fix.

## Information architecture
Four destinations only: **Today**, **Claims**, **Money**, **SHA rules**. Plus one global action, **New claim**.
- Desktop: a deep-navy left sidebar with logo, New claim button, the four destinations, and facility and user at the bottom.
- Mobile PWA: a bottom tab bar with Today, Claims, a raised centre camera button (New claim), Money and Rules.
- No nested menus, no settings maze, no tables as a home screen.

## Key screens
1. **Today.** A greeting, the date, one hero number ("At risk if not fixed today: KSh 127,600"), a "Needs you" list of task cards, and a "Lipwad is working" activity feed with timestamps and citation chips. Resolving a task updates the hero number live.
2. **Claim review.** Evidence on one side (photo with a SAM-highlighted region, waveform with the spoken segment highlighted, or the rule clause with its version), and "What Lipwad found" on the other: every field with a citation chip. Selecting a field shows its proof. One "Ask about this claim" box that answers only from that claim's evidence and the SHA rules, always cited.
3. **Capture (mobile).** A full-screen camera with live document edges, a chip strip of captured documents, a large shutter, a mic button for the voice note, and "Build claim".
4. **Rescue.** Lives inside Today and Claim review, not as its own section: SHA's returned reason in plain words (English or Kiswahili toggle), the proposed fix as a before/after list, a deadline countdown, and a confirmation checkbox that gates resubmission.
5. **Money.** One page with four figures (submitted, at risk, rescued, pending), one simple weekly bar chart and the "closing soon" list. Nothing more.

## Visual direction: "Navy ledger, paper evidence"
- **Ground:** warm paper `#F5F3EE`, white cards `#FFFFFF`, hairline borders `#E2DED4`.
- **Brand:** deep navy. Navy 950 `#06122A` (sidebar, camera, evidence panels), Navy 900 `#0A1F44` (ink, primary buttons, hero), Navy 800 `#13294B`, Navy 700 `#23417A`.
- **Signal accent:** periwinkle `#7FA6FF`, used for active nav, highlights, focus and the primary action on navy. Never for status.
- **Ink:** `#0A1F44`, muted `#4D5A73`.
- **Type:** Schibsted Grotesk (UI and headings; display 40/800 with tight tracking, body 15/400). Martian Mono for every money amount, ID, timestamp and citation chip.
- **Shape:** 12–18 px radii, generous padding, flat surfaces. Shadows only on things that float (bottom sheets, the camera button, photographed documents).

## Alert system (strict)
| Status | Text / background | Meaning |
|---|---|---|
| Ready · Paid | `#0B6B4F` / `#DDF2E8` | All fields cited and rules pass, or money received |
| Needs a fix | `#8A4B00` / `#FFEFCC` | One named, fixable problem |
| Blocked · Returned | `#A3201B` / `#FCE1DE` | Money will be lost; also deadlines under 48 hours |
| With SHA | `#1C4FA8` / `#E1EAFB` | Out of the user's hands; neutral information |

Every status pairs an icon and a word with the colour; colour is never the only signal. Red is rare and always means money is at risk. All text meets 4.5:1 contrast.

## Copy
Plain, specific and kind. Say exactly what is wrong and what to do: "Discharge summary is unsigned on page 2. Ask Dr. Otieno to sign, then snap it." Money is always "KSh 48,500", with no decimals. A Kiswahili toggle on reasons and explanations. Lipwad never gives clinical advice and never adds or upgrades services, and the UI says so near every submit action.

## PWA requirements
Installable (manifest, icons, navy theme colour). Works at 360 px width. Touch targets of 44 px or more. Respects safe areas. Capture queues offline and syncs when the network returns, with a visible "3 waiting to upload" state. Camera and mic permissions are explained before they are requested.

## Accessibility
Real buttons, links and labelled inputs. Visible focus rings in periwinkle. `aria-pressed` on toggles and `aria-current` on nav. Icon-only buttons get labels. Respect reduced motion.

## Don't
No chatbot window or floating chat bubble. No gradient washes, glassmorphism, emoji, stock illustrations or left-border accent cards. No walls of charts or KPI tiles. No fake phone status bars. No real patient data: use synthetic names and the `[demo]` label.
