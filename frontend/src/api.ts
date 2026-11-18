export type Citation = {
  kind: "image" | "audio" | "rule";
  source_id: string;
  region: number[][] | null;
  t_start: number | null;
  t_end: number | null;
  rule_version: string | null;
  quote: string | null;
};
export type Field = { name: string; value: string; confidence: number; citations: Citation[] };
export type Flag = { code: string; severity: "amber" | "red" | "note"; citations: Citation[] };
export type Claim = {
  id: string;
  lifecycle: string;
  readiness: "green" | "amber" | "red" | null;
  hie_id: string | null;
  fields: Field[];
  coded_lines: Field[];
  flags: Flag[];
  resubmission_deadline: string | null;
  review_deadline: string | null;
  submission_deadline: string | null;
};
export type Step = { claim_id: string; at: string; kind: string; text: string; model: string | null };
export type Upload = { id: string; filename: string };
export type ClaimDetail = { claim: Claim; uploads: Upload[]; activity: Step[]; has_corrected_page: boolean };
export type Summary = {
  id: string;
  claim_id?: string;
  patient_name: string | null;
  readiness: Claim["readiness"];
  lifecycle: string;
  reasons: string[];
  actions: string[];
  amount_ksh: number | null;
  deadline: string | null;
  rescue: boolean;
};
export type Today = { at_risk_ksh: number; tasks: Summary[]; activity: Step[] };
export type Rule = {
  id: string;
  title: string;
  issuer: string;
  version: string;
  status: "final" | "news" | "lipwad";
  url: string;
  clause: string;
  quote: string;
  checks: string;
  quote_kind: "verbatim" | "summary";
};
export type AuditEvent = { at: string; actor: string; action: string; detail: Record<string, unknown> };
export type Audit = { claim_id: string; exported_at: string; events: AuditEvent[] };
export type Draft = { reason: string[]; changes: { field: string; before: string | null; after: string }[] };

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) =>
  call<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });

export const api = {
  today: () => call<Today>("/today"),
  claims: () => call<Summary[]>("/claims"),
  rules: () => call<Rule[]>("/rules"),
  audit: (id: string) => call<Audit>(`/claims/${id}/audit`),
  claim: (id: string) => call<ClaimDetail>(`/claims/${id}`),
  run: (id: string) => post<ClaimDetail>(`/claims/${id}/run`),
  submit: (id: string, confirmedBy: string) =>
    post<ClaimDetail>(`/claims/${id}/submit`, { confirmed_by: confirmedBy }),
  rescue: (id: string) => post<Draft>(`/claims/${id}/rescue`),
  resubmit: (id: string, confirmedBy: string) =>
    post<ClaimDetail>(`/claims/${id}/resubmit`, { confirmed_by: confirmedBy }),
};

export const ksh = (amount: number | null) =>
  amount === null ? "—" : `KSh ${amount.toLocaleString("en-KE")}`;

/** A sent back claim has 14 days to resubmit; a rejected one has 7 working days to ask for review. */
export function timeLeft(deadline: string | null, lifecycle: string): string | null {
  if (!deadline) return null;
  const review = lifecycle === "rejected";
  const hours = Math.round((new Date(deadline).getTime() - Date.now()) / 3_600_000);
  if (hours <= 0) return review ? "Review window closed" : "Resubmission window closed";
  if (review) return hours < 48 ? `${hours} hours left to request a review` : `${Math.ceil(hours / 24)} days left to request a review`;
  return hours < 48 ? `${hours} hours left of 14 days to resubmit` : `${Math.ceil(hours / 24)} of 14 days left to resubmit`;
}

const DATE = /^\d{4}-\d{2}-\d{2}$/;

export function display(name: string, value: string): string {
  const v = value.replace(" [demo]", "");
  if (name === "invoice_total" && /^\d+$/.test(v)) return ksh(Number(v));
  if (name === "declaration_signature" || name === "discharge_summary_signature") return v === "present" ? "Signed" : "Not signed";
  if (name === "facility_stamp") return v === "present" ? "Stamped" : "No stamp";
  if (name === "physician_details") return v === "present" ? "Name and registration no. given" : "Missing";
  if (name === "invoice_tariff_codes") return { all: "On every line", some: "On some lines", none: "None printed" }[v] ?? v;
  if (name === "invoice_itemised") return v === "yes" ? "Yes" : "No, total only";
  if (DATE.test(v)) {
    return new Date(`${v}T00:00:00`).toLocaleDateString("en-KE", { day: "numeric", month: "short", year: "numeric" });
  }
  return v;
}

/** Seconds as m:ss, for audio citations. */
export const clock = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;

/** Splits a logged explanation into its English and Kiswahili parts. */
export function explanation(text: string): { en: string; sw: string | null } {
  const [en, sw] = text.split(" | SW: ");
  return { en, sw: sw ?? null };
}

/** The English part of a feed step, for the short feed on Today. */
export const headline = (text: string) => explanation(text).en;

export const patientName = (name: string | null, reviewed: boolean) =>
  name?.replace(" [demo]", "") ?? (reviewed ? "Name unreadable" : "Not read yet");
