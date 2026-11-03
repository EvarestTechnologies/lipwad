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
        The checks Lipwad runs on every claim, each cited by ID and version on the flags it raises.
        The wording below is Lipwad's own description. The SHA source documents are not registered yet,
        so versions show as placeholders and no SHA rule text is quoted.
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
