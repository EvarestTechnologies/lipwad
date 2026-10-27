# Lipwad — Project Brief

**Lipwad gets Kenyan hospitals paid.**

## Problem
Kenyan hospitals deliver care under the Social Health Authority (SHA) and then fail to get paid, mostly over paperwork. Billions of shillings in claims have been rejected or returned, and missing documentation is the leading cause, followed by missing itemised invoices, coding errors and claims time-barred after the 14-day resubmission window. The evidence usually exists, but it is scattered across paper forms, phone photos, lab slips and staff memory, while the rules it must satisfy vary by benefit package, facility level, tariff and date of service. SHA screens claims with an AI fraud engine. Hospitals have nothing working on their side.

## Solution
A multimodal agent that works for the hospital. It turns photos, scans and voice notes in English, Swahili or Sheng into a complete, correctly coded claim, checks it against the SHA rules that apply to that specific claim through agentic retrieval, cites every field to its source (image region, audio timestamp or rule), submits through the national Health Information Exchange (HIE), and repairs rejections before the deadline. A clinician or clerk confirms every claim. The agent never invents, upcodes or gives clinical advice.

## Meta tooling
SAM 3.1 isolates documents in messy photos. Muse Spark vision extracts fields. Muse Voice Transcribe handles voice notes. Muse Spark Open, served on Baseten, runs the reasoning loop.

## Hackathon scope (Oct 27 – Nov 4)
In scope: intake, coding, rules check, verification with click-to-source, HIE sandbox submit/status/edit, and the rescue loop. All data is synthetic.

Out of scope: production HMIS integration, real patient data and payment guarantees.

## Success
A clerk turns a crumpled claim file and a Swahili voice note into a cited, submit-ready claim in under two minutes. Seeded failure cases are caught before submission, and a rejected claim is repaired and resubmitted inside the window.
