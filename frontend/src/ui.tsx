import type { ReactNode } from "react";

import type { Claim } from "./api";
import { navigate } from "./router";

const STATUS = {
  green: { word: "Ready", icon: "✓", tone: "ready" },
  amber: { word: "Needs a fix", icon: "!", tone: "fix" },
  red: { word: "Blocked", icon: "×", tone: "blocked" },
} as const;

export function StatusPill({ readiness, lifecycle }: { readiness: Claim["readiness"]; lifecycle: string }) {
  if (lifecycle === "submitted" || lifecycle === "paid") {
    return <span className="pill sha"><span aria-hidden="true">→</span> With SHA</span>;
  }
  if (lifecycle === "returned" || lifecycle === "rejected") {
    return <span className="pill blocked"><span aria-hidden="true">↺</span> {lifecycle === "returned" ? "Sent back" : "Rejected"}</span>;
  }
  if (!readiness) return <span className="pill neutral">Not reviewed</span>;
  const status = STATUS[readiness];
  return (
    <span className={`pill ${status.tone}`}>
      <span aria-hidden="true">{status.icon}</span> {status.word}
    </span>
  );
}

export const REASON_TEXT: Record<string, string> = {
  signature_missing: "The claim form is unsigned. Ask the clinician to sign, then snap the signed page.",
  itemised_invoice_missing: "The invoice shows a total only. SHA needs each service listed.",
  service_type_inconsistent: "The invoice bills inpatient bed days, but the form records an outpatient visit.",
  practitioner_not_found: "The practitioner number is not in the registry. Check it with the ward.",
  retake_required: "The photo is too unclear to read. Retake it in better light.",
  resubmission_deadline_near: "SHA sent this claim back. Fix and resubmit it within 14 days of the date it was returned.",
  claim_rejected: "SHA rejected this claim. You have 7 working days to request a review with new evidence.",
  voice_note_unclear: "The voice note could not be heard. Record it again somewhere quiet.",
  admission_date_mismatch: "The voice note gives a different admission date from the claim form. Confirm it with the ward.",
  discharge_summary_missing: "No discharge or case summary is on file. SHA needs one with every claim.",
  claim_form_missing: "No claim form is on file. SHA needs one with every claim.",
  invoice_missing: "No itemised invoice or final bill is on file. SHA needs one with every claim.",
  discharge_summary_unsigned: "The discharge summary is not signed. Ask the treating clinician to sign it.",
  voice_needs_review: "Part of the voice note is not in English. Listen to it and enter any details yourself; Lipwad took nothing from it.",
};

export const NO_ADVICE =
  "Lipwad never submits a claim without your OK, and never gives clinical advice.";

export function Link({ to, current, className, children }: { to: string; current?: boolean; className?: string; children: ReactNode }) {
  return (
    <a href={to} className={className} aria-current={current ? "page" : undefined} onClick={(e) => { e.preventDefault(); navigate(to); }}>
      {children}
    </a>
  );
}

export const LABELS: Record<string, string> = {
  patient_name: "Patient name",
  patient_ref: "Patient number",
  visit_type: "Visit type",
  admission_date: "Admitted",
  discharge_date: "Discharged",
  diagnosis: "Diagnosis",
  practitioner_name: "Clinician",
  practitioner_id: "Practitioner number",
  facility_id: "Facility",
  clinician_signature: "Clinician signature",
  invoice_total: "Invoice total",
  invoice_itemised: "Itemised invoice",
  service_code: "Service code",
  voice_admission_date: "Admitted (voice note)",
  discharge_summary_signature: "Discharge summary signature",
};

const SHORT_REASON: Record<string, string> = {
  signature_missing: "unsigned claim form",
  itemised_invoice_missing: "invoice not itemised",
  service_type_inconsistent: "service type does not match the documents",
  practitioner_not_found: "practitioner not in the registry",
  retake_required: "photo too unclear to read",
  resubmission_deadline_near: "sent back, 14-day window closing",
  claim_rejected: "rejected by SHA",
  admission_date_mismatch: "admission dates disagree",
  voice_note_unclear: "voice note could not be heard",
  discharge_summary_missing: "discharge summary missing",
  claim_form_missing: "claim form missing",
  invoice_missing: "invoice missing",
  discharge_summary_unsigned: "discharge summary unsigned",
  voice_needs_review: "voice note needs a person to listen",
};
const DOCUMENTS: Record<string, string> = {
  claim_form_signed: "signed claim form",
  discharge_summary: "discharge summary",
  case_summary: "case summary",
};
const STATUS_WORD: Record<string, string> = { green: "Ready", amber: "Needs a fix", red: "Blocked" };

/** Rewrites an activity step's internal codes and field names in plain words. */
export function plain(text: string): string {
  const status = text.match(/^Status (green|amber|red); reasons: (.*)$/);
  if (status) {
    const reasons = status[2] === "none" ? [] : status[2].split(", ").map((code) => SHORT_REASON[code] ?? code);
    return `${STATUS_WORD[status[1]]}${reasons.length ? `: ${reasons.join(", ")}` : ""}`;
  }
  return text
    .replace(/\b([a-z]+(?:_[a-z]+)+)\b/g, (m) => (LABELS[m] ?? SHORT_REASON[m] ?? DOCUMENTS[m] ?? m.replace(/_/g, " ")).toLowerCase())
    .replace(/ -> /g, " → ");
}
