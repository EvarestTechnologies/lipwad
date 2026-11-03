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
export type Flag = { code: string; severity: "amber" | "red"; citations: Citation[] };
export type Claim = {
  id: string;
  lifecycle: string;
  readiness: "green" | "amber" | "red" | null;
  hie_id: string | null;
  fields: Field[];
  coded_lines: Field[];
  flags: Flag[];
  resubmission_deadline: string | null;
  submission_deadline: string | null;
};
export type Step = { claim_id: string; at: string; kind: string; text: string; model: string | null };
export type Upload = { id: string; filename: string };
export type ClaimDetail = { claim: Claim; uploads: Upload[]; activity: Step[] };
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

export function timeLeft(deadline: string | null): string | null {
  if (!deadline) return null;
  const hours = Math.round((new Date(deadline).getTime() - Date.now()) / 3_600_000);
  if (hours <= 0) return "Window closed";
  if (hours < 48) return `${hours} hours left to resubmit`;
  return `${Math.floor(hours / 24)} days left to resubmit`;
}
