import { useEffect, useState } from "react";

import { api, type Rule } from "./api";

const STATUS: Record<Rule["status"], string> = {
  final: "Official, final as published",
  news: "News report, context only",
  lipwad: "Lipwad check, not an SHA rule",
};

export function RulesScreen() {
  const [rules, setRules] = useState<Rule[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.rules().then(setRules, (e: Error) => setError(e.message)); }, []);

  return (
    <div>
      <h1>SHA rules</h1>
      <p className="muted">
        Every flag Lipwad raises cites one of these rules. Each quote is copied word for word from the
        document named, and the status says how much weight it carries. Lipwad checks the paperwork
        against them; it never decides a claim.
      </p>
      {error && <p className="error" role="alert">{error}</p>}
      <ul className="rules">
        {rules?.map((rule) => (
          <li key={rule.id} id={rule.id}>
            <p className="mono">{rule.id} <span className="chip">{STATUS[rule.status]}</span></p>
            <p>{rule.checks}</p>
            {rule.quote_kind === "summary" ? (
              <p className="summary"><strong>Summary of the Second and Third Schedules:</strong> {rule.quote}</p>
            ) : (
              <blockquote>“{rule.quote}”</blockquote>
            )}
            {rule.url ? (
              <p className="muted">
                {rule.title}, {rule.issuer}. {rule.clause}. {rule.version}.{" "}
                <a href={rule.url} target="_blank" rel="noreferrer">Open the source</a>
              </p>
            ) : (
              <p className="muted">{rule.title}. {rule.version}.</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
