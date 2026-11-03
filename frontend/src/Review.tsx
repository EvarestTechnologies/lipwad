import { useCallback, useEffect, useRef, useState } from "react";

import { api, clock, display, explanation, patientName, timeLeft, type Citation, type ClaimDetail, type Draft, type Field } from "./api";
import { Link, NO_ADVICE, REASON_TEXT, StatusPill } from "./ui";

const LABELS: Record<string, string> = {
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
};

type Selected = { label: string; value: string; citation: Citation };

export function Review({ claimId }: { claimId: string }) {
  const [detail, setDetail] = useState<ClaimDetail | null>(null);
  const [selected, setSelected] = useState<Selected | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [name, setName] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);

  const load = useCallback(async () => {
    try {
      const next = await api.claim(claimId);
      setDetail(next);
      setSelected((current) => current ?? firstEvidence(next));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [claimId]);
  useEffect(() => { load(); }, [load]);

  async function act(label: string, action: () => Promise<unknown>) {
    setBusy(label);
    setError(null);
    try {
      await action();
      setConfirmed(false);
      setSelected(null);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (!detail) return <p className="muted">{error ?? "Loading…"}</p>;
  const { claim } = detail;
  const rescue = claim.lifecycle === "returned" || claim.lifecycle === "rejected";
  const canSubmit = claim.readiness === "green" && claim.lifecycle === "draft";
  const patient = patientName(claim.fields.find((f) => f.name === "patient_name")?.value ?? null, claim.readiness !== null);
  const fields = [...claim.fields, ...claim.coded_lines].filter((f) => !f.name.startsWith("invoice_line"));

  function select(field: Field) {
    const citation = field.citations.find((c) => c.kind === "image") ?? field.citations[0];
    setSelected(evidenceFor(field, citation));
  }

  return (
    <div className="review">
      <p className="crumbs"><Link to="/claims">Claims</Link> / <span className="mono">{claim.id}</span></p>
      <header className="review-head">
        <div>
          <h1>{patient}</h1>
          <StatusPill readiness={claim.readiness} lifecycle={claim.lifecycle} />
          {claim.resubmission_deadline && <span className="deadline"> {timeLeft(claim.resubmission_deadline)}</span>}
        </div>
        <button className="secondary" disabled={busy !== null} onClick={() => act("run", () => api.run(claim.id))}>
          {busy === "run" ? "Lipwad is reading…" : claim.readiness ? "Review again" : "Review with Lipwad"}
        </button>
      </header>
      {error && <p className="error" role="alert">{error}</p>}

      {claim.flags.length > 0 && (
        <ul className="flags">
          {claim.flags.map((flag) => (
            <li key={flag.code} className={flag.severity === "red" ? "flag blocked" : "flag fix"}>
              <strong>{REASON_TEXT[flag.code] ?? flag.code}</strong>
              <span className="cites">
                {flag.citations.map((c, i) => (
                  <button key={i} className="chip" onClick={() => setSelected({ label: c.kind === "rule" ? c.source_id : c.kind === "audio" ? "Voice note" : "Photo region", value: c.quote ?? "", citation: c })}>
                    {c.kind === "rule" ? `${c.source_id} · ${c.rule_version}`
                      : c.kind === "audio" ? `Voice ${clock(c.t_start ?? 0)}–${clock(c.t_end ?? 0)}`
                      : "Photo region"}
                  </button>
                ))}
              </span>
            </li>
          ))}
        </ul>
      )}

      <div className="columns">
        <section className="evidence" aria-label="Evidence">
          <h2>Evidence {selected ? `· ${selected.label}` : ""}</h2>
          {selected?.citation.kind === "rule" ? (
            <div className="rule">
              <p className="mono">{selected.citation.source_id} · {selected.citation.rule_version}</p>
              <p>Rule text is a placeholder until the SHA source document is registered in docs/SOURCES.md.</p>
            </div>
          ) : selected?.citation.kind === "audio" ? (
            <VoiceClip citation={selected.citation} />
          ) : selected ? (
            <figure className="photo">
              <img src={`/api/uploads/${selected.citation.source_id}/image`} alt={`Document for ${selected.label}`} />
              {selected.citation.region && <Highlight region={selected.citation.region} />}
              <figcaption className="mono">Source: {selected.citation.source_id}</figcaption>
            </figure>
          ) : (
            <p className="muted">Tap a field to see exactly where it came from.</p>
          )}
        </section>

        <section className="found" aria-label="What Lipwad found">
          <h2>What Lipwad found</h2>
          {fields.length === 0 && <p className="muted">Not reviewed yet.</p>}
          <ul>
            {fields.map((field) => (
              <li key={field.name}>
                <button className="field" aria-pressed={selected?.label === (LABELS[field.name] ?? field.name)} onClick={() => select(field)}>
                  <span className="label">{LABELS[field.name] ?? field.name}</span>
                  <span className="value">{display(field.name, field.value)}</span>
                  <span className="chip">{field.citations.length} source{field.citations.length === 1 ? "" : "s"}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {rescue && (
        <section className="rescue" aria-label="Rescue">
          <h2>Rescue</h2>
          {!draft ? (
            <button disabled={busy !== null} onClick={() => act("rescue", async () => setDraft(await api.rescue(claim.id)))}>
              {busy === "rescue" ? "Reading the signed page…" : "Read the signed page"}
            </button>
          ) : (
            <>
              <p>SHA's reason: {draft.reason.map((r) => REASON_TEXT[r] ?? r).join(" ")}</p>
              <table>
                <thead><tr><th>Field</th><th>Before</th><th>After</th></tr></thead>
                <tbody>
                  {draft.changes.map((c) => (
                    <tr key={c.field}><td>{LABELS[c.field] ?? c.field}</td><td>{c.before ? display(c.field, c.before) : "—"}</td><td>{display(c.field, c.after)}</td></tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </section>
      )}

      {(canSubmit || (rescue && draft)) && (
        <section className="confirm" aria-label="Confirm">
          <label>Your name <input value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label className="check">
            <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
            I have checked every field against its source.
          </label>
          <button
            disabled={!confirmed || !name.trim() || busy !== null}
            onClick={() => act("submit", () => (rescue ? api.resubmit(claim.id, name) : api.submit(claim.id, name)))}
          >
            {rescue ? "Approve fix & resubmit" : "OK & submit to SHA"}
          </button>
          <p className="guardrail">{NO_ADVICE}</p>
        </section>
      )}

      <section aria-label="Activity">
        <h2>Lipwad's steps</h2>
        <ol className="feed">
          {detail.activity.map((step, i) => (
            <li key={i}>
              <time className="mono">{new Date(step.at).toLocaleTimeString("en-KE", { hour: "2-digit", minute: "2-digit" })}</time>
              <Explained text={step.text} />
              {step.model && <span className="chip model">{step.model}</span>}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}

function VoiceClip({ citation }: { citation: Citation }) {
  const audio = useRef<HTMLAudioElement>(null);
  const clipping = useRef(false);
  const start = citation.t_start ?? 0;
  const end = citation.t_end ?? start;
  function play() {
    if (!audio.current) return;
    clipping.current = true;
    audio.current.currentTime = start;
    void audio.current.play();
  }
  // Stop at the end of the cited span only when the clip button started it, so the
  // native controls can still play the whole note.
  function stopAtEnd() {
    if (clipping.current && audio.current && audio.current.currentTime >= end) {
      clipping.current = false;
      audio.current.pause();
    }
  }
  return (
    <div className="voice">
      <audio ref={audio} src={`/api/uploads/${citation.source_id}/file`} preload="auto" onTimeUpdate={stopAtEnd} onSeeking={() => { if (audio.current && Math.abs(audio.current.currentTime - start) > 0.5) clipping.current = false; }} controls />
      <button onClick={play}>Play {clock(start)}–{clock(end)}</button>
      {citation.quote && <blockquote>“{citation.quote}”</blockquote>}
      <p className="mono">Source: {citation.source_id} · Muse Voice Transcribe</p>
    </div>
  );
}

function Explained({ text }: { text: string }) {
  const { en, sw } = explanation(text);
  return (
    <span className="explained">
      <span>{en}</span>
      {sw && <span lang="sw" className="muted">{sw}</span>}
    </span>
  );
}

function evidenceFor(field: Field, citation: Citation): Selected {
  return { label: LABELS[field.name] ?? field.name, value: field.value, citation };
}

/** Opens the evidence panel on the first flagged photo region, or the first field. */
function firstEvidence(detail: ClaimDetail): Selected | null {
  for (const flag of detail.claim.flags) {
    const citation = flag.citations.find((c) => c.kind === "image");
    if (citation) {
      const same = (c: Citation) => c.source_id === citation.source_id && JSON.stringify(c.region) === JSON.stringify(citation.region);
      const field = detail.claim.fields.find((f) => f.citations.some(same));
      return field ? evidenceFor(field, citation) : { label: "Photo region", value: "", citation };
    }
  }
  const field = detail.claim.fields.find((f) => f.citations.some((c) => c.kind === "image"));
  return field ? evidenceFor(field, field.citations.find((c) => c.kind === "image")!) : null;
}

function Highlight({ region }: { region: number[][] }) {
  const xs = region.map((p) => p[0]);
  const ys = region.map((p) => p[1]);
  const left = Math.min(...xs) * 100;
  const top = Math.min(...ys) * 100;
  return (
    <span
      className="highlight"
      style={{ left: `${left}%`, top: `${top}%`, width: `${Math.max(...xs) * 100 - left}%`, height: `${Math.max(...ys) * 100 - top}%` }}
      aria-hidden="true"
    />
  );
}
