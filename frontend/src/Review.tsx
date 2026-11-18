import { useCallback, useEffect, useRef, useState } from "react";

import { api, clock, display, explanation, patientName, timeLeft, type AuditEvent, type Citation, type ClaimDetail, type Draft, type Field } from "./api";
import { FIX_STEP, LABELS, Link, NO_ADVICE, onlyAttachments, Page, plain, REASON_TEXT, StatusPill } from "./ui";


type Selected = { label: string; value: string; citation: Citation };

export function Review({ claimId }: { claimId: string }) {
  const [detail, setDetail] = useState<ClaimDetail | null>(null);
  const [selected, setSelected] = useState<Selected | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [name, setName] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("found");
  const evidenceRef = useFitToPhoto(selected?.citation.kind === "image");

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

  if (!detail) return <Page title="Claim"><p className="muted">{error ?? "Loading…"}</p></Page>;
  const { claim } = detail;
  const rescue = claim.lifecycle === "returned" || claim.lifecycle === "rejected";
  const withSha = claim.lifecycle === "submitted" || claim.lifecycle === "paid";
  const corrected = claim.fields.some((f) => f.citations.some((c) => c.source_id.endsWith("-claim_form_signed")));
  const canFix = !withSha && !corrected && detail.has_corrected_page && (rescue || claim.readiness !== null);
  const canSubmit = claim.readiness === "green" && claim.lifecycle === "draft";
  const patient = patientName(claim.fields.find((f) => f.name === "patient_name")?.value ?? null, claim.readiness !== null);
  // Invoice lines show as evidence chips; the service code row is covered by "Tariff codes on invoice".
  const fields = [...claim.fields, ...claim.coded_lines].filter((f) => !f.name.startsWith("invoice_line") && f.name !== "service_code");
  /** Names a photo citation after the field it came from, such as "Invoice line 1". */
  const chipLabel = (c: Citation) => {
    const same = (x: Citation) => x.source_id === c.source_id && x.quote === c.quote && JSON.stringify(x.region) === JSON.stringify(c.region);
    const owner = claim.fields.find((f) => f.name.startsWith("invoice_line") && f.citations.some(same))
      ?? claim.fields.find((f) => f.citations.some(same));
    return owner ? label(owner.name) : "Photo region";
  };

  function select(field: Field) {
    const citation = field.citations.find((c) => c.kind === "image") ?? field.citations[0];
    setSelected(evidenceFor(field, citation));
  }

  const deadline = claim.resubmission_deadline ?? claim.review_deadline;
  const showFix = canFix || (draft && !withSha) || (rescue && !corrected);
  const showConfirm = canSubmit || (rescue && corrected);
  // A draft that needs a fix the corrected-page flow does not cover gets a plain checklist.
  const toFix = claim.flags.filter((f) => f.severity !== "note" && !["resubmission_deadline_near", "claim_rejected"].includes(f.code));
  const showChecklist = claim.lifecycle === "draft" && claim.readiness !== "green" && claim.readiness !== null && toFix.length > 0 && !showFix;
  const flagItems = claim.flags.map((flag) => (
    <li key={flag.code} className={flag.severity === "red" ? "flag blocked" : flag.severity === "note" ? "flag note" : "flag fix"}>
      <strong>{REASON_TEXT[flag.code] ?? flag.code}</strong>
      <span className="cites">
        {flag.citations.map((c, i) => (
          <button key={i} className="chip" onClick={() => setSelected({ label: c.kind === "rule" ? c.source_id : c.kind === "audio" ? "Voice note" : chipLabel(c), value: c.quote ?? "", citation: c })}>
            {c.kind === "rule" ? `${c.source_id} · ${c.rule_version}`
              : c.kind === "audio" ? `Voice ${clock(c.t_start ?? 0)}–${clock(c.t_end ?? 0)}`
              : chipLabel(c)}
          </button>
        ))}
      </span>
    </li>
  ));

  return (
    <Page
      crumbs={<><Link to="/claims">Claims</Link> / <span className="mono">{claim.id}</span></>}
      title={patient}
      meta={
        <span className="title-meta">
          <StatusPill readiness={claim.readiness} lifecycle={claim.lifecycle} />
          {deadline && <span className="deadline">{timeLeft(deadline, claim.lifecycle)}</span>}
        </span>
      }
      actions={!withSha && !(rescue && corrected) && (
        <button className="secondary" disabled={busy !== null} onClick={() => act("run", () => api.run(claim.id))}>
          {busy === "run" ? "Lipwad is reading…" : claim.readiness ? "Review again" : "Review with Lipwad"}
        </button>
      )}
      top={(error || claim.flags.length > 0) && (
        <>
          {error && <p className="error" role="alert">{error}</p>}
          {claim.flags.length > 2 ? (
            <details className="flag-summary">
              <summary>
                <strong>{claim.flags.length} findings:</strong>{" "}
                {claim.flags.map((f) => plain(f.code)).join(", ")}
                <span className="show-all">Show all</span>
              </summary>
              <ul className="flags">{flagItems}</ul>
            </details>
          ) : (
            claim.flags.length > 0 && <ul className="flags">{flagItems}</ul>
          )}
        </>
      )}
      bodyClass="claim-body"
    >
      <section className="evidence" aria-label="Evidence" ref={evidenceRef}>
        <h2>Evidence {selected ? `· ${selected.label}` : ""}</h2>
        <div className="evidence-view">
          {selected?.citation.kind === "rule" ? (
            <div className="rule">
              <p className="mono">{selected.citation.source_id} · {selected.citation.rule_version}</p>
              {selected.citation.quote && <blockquote>“{selected.citation.quote}”</blockquote>}
              <p><Link to="/rules">See the source and status on the Rules page</Link></p>
            </div>
          ) : selected?.citation.kind === "audio" ? (
            <VoiceClip citation={selected.citation} />
          ) : selected ? (
            <figure className="photo">
              <div className="photo-frame">
                <img src={`/api/uploads/${selected.citation.source_id}/image`} alt={`Document for ${selected.label}`} />
                {selected.citation.region && <Highlight region={selected.citation.region} />}
              </div>
              <figcaption className="mono">Source: {selected.citation.source_id}</figcaption>
            </figure>
          ) : (
            <p className="muted">Tap a field to see exactly where it came from.</p>
          )}
        </div>
      </section>

      <section className="side" aria-label="Claim details">
        <div className="tabs" role="tablist" aria-label="Claim details">
          {TABS.map((t) => (
            <button key={t.id} role="tab" id={`tab-${t.id}`} aria-selected={tab === t.id} aria-controls={`panel-${t.id}`} className="tab" onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>
        <div className="tab-panel" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} tabIndex={0}>
          {tab === "found" && (
            <div className="found">
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
            </div>
          )}
          {tab === "steps" && (
            <ol className="feed">
              {detail.activity.map((step, i) => (
                <li key={i}>
                  <time className="mono">{new Date(step.at).toLocaleTimeString("en-KE", { hour: "2-digit", minute: "2-digit" })}</time>
                  <Explained text={step.text} />
                  {step.model && <span className="chip model">{step.model}</span>}
                </li>
              ))}
            </ol>
          )}
          {tab === "history" && <History claimId={claim.id} version={detail.activity.length} />}
        </div>

        {(showFix || showConfirm || showChecklist) && (
          <div className="dock">
            {showChecklist && (
              <section className="rescue" aria-label="What to fix">
                <h2>What to fix</h2>
                <ul className="fix-list">
                  {toFix.map((f) => <li key={f.code}>{FIX_STEP[f.code] ?? REASON_TEXT[f.code] ?? f.code}</li>)}
                </ul>
                <button className="secondary" disabled={busy !== null} onClick={() => act("run", () => api.run(claim.id))}>
                  {busy === "run" ? "Lipwad is reading…"
                    : onlyAttachments(toFix.map((f) => f.code)) ? "I've attached it, review again" : "I've made the fix, review again"}
                </button>
                <p className="guardrail">Lipwad never fills anything in. A person makes every fix. {NO_ADVICE}</p>
              </section>
            )}
            {showFix && (
              <section className="rescue" aria-label={rescue ? "Rescue" : "Fix"}>
                <h2>{rescue ? "Rescue" : "Fix"}</h2>
                {!draft && canFix ? (
                  <button disabled={busy !== null} onClick={() => act("rescue", async () => setDraft(await api.rescue(claim.id)))}>
                    {busy === "rescue" ? "Reading the signed page…" : "Read the signed page"}
                  </button>
                ) : !draft ? (
                  <p className="muted">No corrected page has been added for this claim yet.</p>
                ) : (
                  <>
                    <p>{rescue ? "SHA's reason" : "What needed fixing"}: {draft.reason.map((r) => REASON_TEXT[r] ?? r).join(" ")}</p>
                    <table>
                      <thead><tr><th>Field</th><th>Before</th><th>After</th></tr></thead>
                      <tbody>
                        {draft.changes.map((c) => (
                          <tr key={c.field}><td>{LABELS[c.field] ?? c.field}</td><td>{c.before ? display(c.field, c.before) : "—"}</td><td>
                              <button className="chip" onClick={() => { const f = claim.fields.find((x) => x.name === c.field); if (f) select(f); }}>
                                {display(c.field, c.after)} · see source
                              </button>
                            </td></tr>
                        ))}
                      </tbody>
                    </table>
                  </>
                )}
              </section>
            )}
            {showConfirm && (
              <section className="confirm" aria-label="Confirm">
                <div className="confirm-row">
                  <label>Your name <input value={name} onChange={(e) => setName(e.target.value)} /></label>
                  <label className="check">
                    <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
                    I have checked every field against its source.
                  </label>
                </div>
                <button
                  disabled={!confirmed || !name.trim() || busy !== null}
                  onClick={() => act("submit", async () => {
                    await (rescue ? api.resubmit(claim.id, name) : api.submit(claim.id, name));
                    setDraft(null);
                  })}
                >
                  {rescue ? "Approve fix & resubmit" : "OK & submit to SHA"}
                </button>
                <p className="guardrail">{NO_ADVICE}</p>
              </section>
            )}
          </div>
        )}
      </section>
    </Page>
  );
}

const PAGE_RATIO = 1240 / 1754; // width / height of the synthetic document photos

/**
 * Shrinks the evidence panel to the photo when the column is too narrow for the photo to
 * fill its height, so no empty dark space is left under it.
 */
function useFitToPhoto(active: boolean) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const panel = ref.current;
    const area = panel?.parentElement;
    if (!panel || !area) return;
    const fit = () => {
      panel.style.maxHeight = "";
      const view = panel.querySelector<HTMLElement>(".evidence-view");
      if (!active || !view) return;
      const chrome = panel.offsetHeight - view.clientHeight;
      const photo = view.clientWidth / PAGE_RATIO + 34; // the 34px holds the source caption
      if (photo < view.clientHeight) panel.style.maxHeight = `${Math.ceil(chrome + photo)}px`;
    };
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(area);
    return () => observer.disconnect();
  }, [active]);
  return ref;
}

const TABS = [
  { id: "found", label: "What Lipwad found" },
  { id: "steps", label: "Lipwad's steps" },
  { id: "history", label: "Full history" },
] as const;

/** The claim's append-only audit trail, from the first photo read to the person who confirmed. */
function History({ claimId, version }: { claimId: string; version: number }) {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  useEffect(() => { api.audit(claimId).then((a) => setEvents(a.events), () => setEvents(null)); }, [claimId, version]);
  if (!events?.length) return <p className="muted">No history yet.</p>;
  return (
    <div className="history">
      <p className="muted">
        {events.length} entries: every file read, every value found with its source, every flag with its rule, and who
        confirmed. Entries are never changed or deleted. <a href={`/api/claims/${claimId}/audit`} download>Download as a file</a>
      </p>
      <ol className="feed">
        {events.map((event, i) => (
          <li key={i}>
            <time className="mono">{new Date(event.at).toLocaleString("en-KE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</time>
            <span>{describe(event)}</span>
            <span className="chip">{event.actor}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function describe(event: AuditEvent): string {
  const d = event.detail as Record<string, string | string[] | null>;
  const rules = Array.isArray(d.rules) ? d.rules.join(", ") : "";
  switch (event.action) {
    case "file_read": return `Read ${String(d.file)}${d.model ? ` with ${d.model}` : ""}`;
    case "value_extracted": return `Found ${label(String(d.field))}: ${display(String(d.field), String(d.value))}`;
    case "flag_raised": return `Flagged: ${plain(String(d.code))} (${rules})`;
    case "flag_cleared": return `Cleared: ${plain(String(d.code))}`;
    case "claim_confirmed": return `Confirmed: “${d.statement}”`;
    case "submitted": return `Sent to SHA, outcome: ${d.outcome}`;
    case "resubmitted": return `Resubmitted to SHA, outcome: ${d.outcome}`;
    default: return event.action;
  }
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
  const shown = plain(en);
  return (
    <span className="explained">
      <span>{shown}</span>
      {sw && <span lang="sw" className="muted">{sw}</span>}
    </span>
  );
}

function label(name: string): string {
  return LABELS[name] ?? name.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

function evidenceFor(field: Field, citation: Citation): Selected {
  return { label: label(field.name), value: field.value, citation };
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
