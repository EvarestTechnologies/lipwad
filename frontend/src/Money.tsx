import { useEffect, useState } from "react";

import { api, ksh, type Summary } from "./api";

const STAGES: { label: string; note: string; match: (c: Summary) => boolean }[] = [
  { label: "Not reviewed", note: "Claim files Lipwad has not read yet", match: (c) => !c.readiness && c.lifecycle === "draft" },
  { label: "Needs a fix", note: "Drafts with a named fix or a block", match: (c) => c.lifecycle === "draft" && !!c.readiness && c.readiness !== "green" },
  { label: "Ready for your OK", note: "Green drafts waiting for a person", match: (c) => c.lifecycle === "draft" && c.readiness === "green" },
  { label: "Returned or rejected", note: "Sent back by SHA, waiting for a fix and resubmission", match: (c) => c.lifecycle === "returned" || c.lifecycle === "rejected" },
  { label: "With SHA", note: "Submitted, waiting for an outcome", match: (c) => c.lifecycle === "submitted" },
  { label: "Paid", note: "Settled by SHA", match: (c) => c.lifecycle === "paid" },
];

export function MoneyScreen() {
  const [claims, setClaims] = useState<Summary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.claims().then(setClaims, (e: Error) => setError(e.message)); }, []);

  return (
    <div>
      <h1>Money</h1>
      <p className="muted">Where each claim's shillings stand. Amounts are invoice totals read from the documents.</p>
      {error && <p className="error" role="alert">{error}</p>}
      <ul className="rows">
        {STAGES.map((stage) => {
          const items = claims?.filter(stage.match) ?? [];
          const total = items.reduce((sum, c) => sum + (c.amount_ksh ?? 0), 0);
          return (
            <li key={stage.label}>
              <span className="who"><strong>{stage.label}</strong><span className="muted">{stage.note}</span></span>
              <span className="mono">{claims ? `${items.length} claim${items.length === 1 ? "" : "s"}` : "…"}</span>
              <span className="money">{!claims ? "…" : items.some((c) => c.amount_ksh !== null) ? ksh(total) : "—"}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
