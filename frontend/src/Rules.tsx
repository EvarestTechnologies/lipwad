import { useEffect, useState } from "react";

import { api, type Rule } from "./api";

export function RulesScreen() {
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.rules().then(setRules, (e: Error) => setError(e.message)); }, []);

  return (
    <div>
      <h1>SHA rules</h1>
      <p className="muted">
        The checks Lipwad runs on every claim. Each flag cites one of these rule IDs with its version.
        The SHA source documents are not registered yet, so the IDs and versions are placeholders, the
        descriptions say what Lipwad checks, and no SHA rule text is quoted.
      </p>
      {error && <p className="error" role="alert">{error}</p>}
      <ul className="rows">
        {rules?.map((rule) => (
          <li key={rule.id}>
            <span className="who"><span className="mono">{rule.id}</span><span>{rule.checks}</span></span>
            <span className="chip">{rule.version}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
