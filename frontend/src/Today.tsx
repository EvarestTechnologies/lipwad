import { useCallback, useEffect, useState } from "react";

import { api, ksh, timeLeft, type Summary, type Today } from "./api";
import { navigate } from "./App";
import { NO_ADVICE, REASON_TEXT, StatusPill } from "./ui";

export function TodayScreen() {
  const [today, setToday] = useState<Today | null>(null);
  const [claims, setClaims] = useState<Summary[]>([]);
  const [running, setRunning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [t, c] = await Promise.all([api.today(), api.claims()]);
      setToday(t);
      setClaims(c);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function review(id: string) {
    setRunning(id);
    setError(null);
    try {
      await api.run(id);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(null);
    }
  }

  const unreviewed = claims.filter((c) => !c.readiness);
  const ready = claims.filter((c) => c.readiness === "green" && c.lifecycle === "draft");
  const date = new Date().toLocaleDateString("en-KE", { weekday: "short", day: "numeric", month: "short", year: "numeric" });

  return (
    <div className="today">
      <p className="eyebrow">{date}</p>
      <h1>Habari. Here is what needs you today.</h1>

      <section className="hero" aria-label="Money at risk">
        <span>At risk if not fixed today</span>
        <strong className="money">{ksh(today?.at_risk_ksh ?? 0)}</strong>
        <span>{today?.tasks.length ?? 0} claims need a person · {ready.length} ready for your OK</span>
      </section>

      {error && <p className="error" role="alert">{error}</p>}

      <section aria-labelledby="needs-you">
        <h2 id="needs-you">Needs you</h2>
        {today?.tasks.length === 0 && <p className="muted">Nothing needs you right now.</p>}
        <ul className="tasks">
          {today?.tasks.map((task) => (
            <li key={task.id} className="task">
              <div className="task-head">
                <StatusPill readiness={task.readiness} lifecycle={task.lifecycle} />
                <span className="mono">{task.id}</span>
                <span className="money">{ksh(task.amount_ksh)}</span>
              </div>
              <strong>{task.patient_name?.replace(" [demo]", "") ?? task.id}</strong>
              <p>{REASON_TEXT[task.reasons[0]] ?? task.reasons[0]}</p>
              {task.deadline && <p className="deadline">{timeLeft(task.deadline)}</p>}
              <button onClick={() => navigate(`/claims/${task.id}`)}>{task.rescue ? "Open rescue" : task.actions[0]}</button>
            </li>
          ))}
        </ul>
      </section>

      {ready.length > 0 && (
        <section aria-labelledby="ready">
          <h2 id="ready">Ready for your OK</h2>
          <ul className="rows">
            {ready.map((c) => (
              <li key={c.id}>
                <span className="mono">{c.id}</span>
                <span>{c.patient_name?.replace(" [demo]", "")}</span>
                <span className="money">{ksh(c.amount_ksh)}</span>
                <button className="secondary" onClick={() => navigate(`/claims/${c.id}`)}>Review</button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {unreviewed.length > 0 && (
        <section aria-labelledby="new">
          <h2 id="new">New claim files</h2>
          <ul className="rows">
            {unreviewed.map((c) => (
              <li key={c.id}>
                <span className="mono">{c.id}</span>
                <StatusPill readiness={c.readiness} lifecycle={c.lifecycle} />
                <button className="secondary" disabled={running !== null} onClick={() => review(c.id)}>
                  {running === c.id ? "Lipwad is reading…" : "Review with Lipwad"}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="feed">
        <h2 id="feed">Lipwad is working</h2>
        <ol className="feed">
          {today?.activity.map((step, index) => (
            <li key={index}>
              <time className="mono">{new Date(step.at).toLocaleTimeString("en-KE", { hour: "2-digit", minute: "2-digit" })}</time>
              <span className="mono chip">{step.claim_id}</span>
              <span>{step.text}</span>
              {step.model && <span className="chip model">{step.model}</span>}
            </li>
          ))}
        </ol>
      </section>
      <p className="guardrail">{NO_ADVICE}</p>
    </div>
  );
}
