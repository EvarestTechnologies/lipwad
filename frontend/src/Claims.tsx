import { useEffect, useState } from "react";

import { api, ksh, patientName, timeLeft, type Summary } from "./api";
import { navigate } from "./App";
import { REASON_TEXT, StatusPill } from "./ui";

export function ClaimsScreen() {
  const [claims, setClaims] = useState<Summary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.claims().then(setClaims, (e: Error) => setError(e.message)); }, []);

  return (
    <div>
      <h1>Claims</h1>
      {error && <p className="error" role="alert">{error}</p>}
      {!claims && !error && <p className="muted">Loading…</p>}
      <ul className="rows claims">
        {claims?.map((c) => (
          <li key={c.id}>
            <button className="row-link" onClick={() => navigate(`/claims/${c.id}`)}>
              <span className="mono">{c.id}</span>
              <span className="who">
                <strong>{patientName(c.patient_name, c.readiness !== null)}</strong>
                <span className="muted">
                  {c.reasons[0] ? REASON_TEXT[c.reasons[0]] ?? c.reasons[0] : c.readiness ? "No issues found" : "Waiting for review"}
                </span>
                {c.deadline && <span className="deadline">{timeLeft(c.deadline)}</span>}
              </span>
              <StatusPill readiness={c.readiness} lifecycle={c.lifecycle} />
              <span className="money">{ksh(c.amount_ksh)}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
