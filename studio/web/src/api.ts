import type {
  AskBackend,
  AskResult,
  Decision,
  FeedbackRow,
  FounderProfile,
  FunnelReport,
  Idea,
  IdeaLineage,
  Overview,
  RerunResult,
  RunFunnel,
  RunSummary,
  Signal,
  StageDrill,
  TraceEntry,
  Version,
  WhatifBackend,
  WhatifJudgeResult,
} from "./types";

const enc = encodeURIComponent;

const vq = (version?: string) => (version ? `?version=${encodeURIComponent(version)}` : "");

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const msg = await res.json().catch(() => ({}));
    throw new Error((msg as { error?: string }).error || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  me: () => req<{ auth: boolean; authed: boolean }>("/api/me"),
  login: (password: string) =>
    req<{ ok: boolean }>("/api/login", { method: "POST", body: JSON.stringify({ password }) }),
  logout: () => req<unknown>("/api/logout", { method: "POST" }),

  versions: () => req<Version[]>("/api/versions"),
  overview: (version?: string) => req<Overview>(`/api/overview${vq(version)}`),
  ideas: (version?: string) => req<Idea[]>(`/api/ideas${vq(version)}`),
  decisions: (version?: string) => req<Decision[]>(`/api/decisions${vq(version)}`),
  signals: () => req<Signal[]>("/api/signals"),

  generate: (body: Record<string, unknown>) =>
    req<{ raw_count: number; signal_count: number; deduped_count: number; candidate_count: number }>(
      "/api/run/generate",
      { method: "POST", body: JSON.stringify(body) },
    ),
  evaluate: (body: Record<string, unknown>) =>
    req<{ evaluated: number; pursue: number; review: number; killed: number }>("/api/run/evaluate", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  inbox: (body: Record<string, unknown>) =>
    req<{ ok: boolean }>("/api/inbox", { method: "POST", body: JSON.stringify(body) }),

  founderProfile: () => req<FounderProfile>("/api/founder-profile"),
  saveFounderProfile: (body: FounderProfile) =>
    req<{ ok: boolean }>("/api/founder-profile", { method: "PUT", body: JSON.stringify(body) }),

  // pipeline-v2 §6 M6: ledger (funnel / trace / founder-labels) + scoped what-if.
  funnel: () => req<FunnelReport>("/api/ledger/funnel"),
  ledgerVerdicts: () => req<Record<string, unknown>[]>("/api/ledger/verdicts"),
  ledgerOutcomes: () => req<Record<string, unknown>[]>("/api/ledger/outcomes"),
  trace: (runId: string, stage: string) =>
    req<TraceEntry[]>(`/api/ledger/trace?run_id=${encodeURIComponent(runId)}&stage=${encodeURIComponent(stage)}`),
  label: (candidateId: string, action: string, extra?: Record<string, unknown>) =>
    req<{ ok: boolean }>("/api/ledger/label", {
      method: "POST",
      body: JSON.stringify({ candidate_id: candidateId, action, ...extra }),
    }),
  whatifJudge: (ideaId: string, overrides: Record<string, unknown>, backend: WhatifBackend = "mock") =>
    req<WhatifJudgeResult>("/api/run/whatif-judge", {
      method: "POST",
      body: JSON.stringify({ idea_id: ideaId, overrides, backend }),
    }),

  // Studio v2: run-centric observability (funnel → stage drill → idea lineage → ask).
  runs: () => req<RunSummary[]>("/api/runs"),
  run: (runId: string) => req<RunFunnel>(`/api/run/${enc(runId)}`),
  stageDrill: (runId: string, stage: string) =>
    req<StageDrill>(`/api/run/${enc(runId)}/stage/${enc(stage)}`),
  ideaLineage: (runId: string, ideaId: string) =>
    req<IdeaLineage>(`/api/run/${enc(runId)}/idea/${enc(ideaId)}`),
  rerunStage: (body: Record<string, unknown>) =>
    req<RerunResult>("/api/run/stage", { method: "POST", body: JSON.stringify(body) }),
  ask: (runId: string, ideaId: string, question: string, backend: AskBackend = "router") =>
    req<AskResult>("/api/ask", {
      method: "POST",
      body: JSON.stringify({ run_id: runId, idea_id: ideaId, question, backend }),
    }),
  // Rich founder feedback: problem-locating labels + free-text note, stored with
  // a frozen lineage snapshot as case-data for manual CC-driven optimization.
  feedback: (runId: string, ideaId: string, labels: string[], note: string) =>
    req<{ ok: boolean; feedback_id: string }>("/api/feedback", {
      method: "POST",
      body: JSON.stringify({ run_id: runId, idea_id: ideaId, labels, note }),
    }),
  feedbackFor: (runId: string, ideaId: string) =>
    req<FeedbackRow[]>(`/api/feedback?run_id=${enc(runId)}&idea_id=${enc(ideaId)}`),
};
