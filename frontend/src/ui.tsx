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
    return <span className="pill blocked"><span aria-hidden="true">↺</span> {lifecycle === "returned" ? "Returned" : "Rejected"}</span>;
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
  service_outside_facility_level: "Inpatient care is billed at a facility level that does not cover it.",
  retake_required: "The photo is too unclear to read. Retake it in better light.",
  resubmission_deadline_near: "SHA returned this claim and the resubmission window closes soon.",
  claim_rejected: "SHA rejected this claim. Review the reason and resubmit.",
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
