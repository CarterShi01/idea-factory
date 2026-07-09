// Shared types — mirror the kernel's JSON shapes (idea_core/models, idea_eval).

export type Factors = Record<string, number>;

export interface Idea {
  id: string;
  signal_id: string;
  source: string;
  title: string;
  pain: string;
  solution: string;
  target_user: string;
  observed_on: string;
  confidence: string;
  category: string | null;
  factors: Factors;
  alpha: number;
  decay: number;
  // generate-stage narrative fields (present on candidates.json / ideas.json items)
  mechanism?: string;
  why_now?: string;
  mvp_week1?: string;
  why_only_me?: string;
  first_10_customers?: string;
  copy_fails_because?: string;
  fusion_sources?: string[];
}

export type Verdict = "pursue" | "review" | "kill";

export interface Evidence {
  id: string;
  candidate_id: string;
  kind: string;
  source_url: string;
  source_date: string;
  fetched_at: string;
  summary: string;
  numbers: Record<string, unknown>;
  valid: boolean;
}

export interface JudgeReason {
  claim: string;
  evidence_ids: string[];
}

export interface PersonaObjection {
  persona: string;
  objection: string;
}

export interface Decision {
  idea_id: string;
  title: string;
  verdict: Verdict;
  eval_score: number;
  killed_by: string[];
  riskiest_assumption: string;
  cheap_experiment: string;
  risk_flags: string[];
  confidence: string;
  factors: Factors;
  killer_objection: string;
  judged_by: "rule" | "llm";
  // pipeline-v2 additions (§5④⑤⑥) — present only when the run used
  // idea-eval's opt-in --require-evidence / --persona-pressure-backend.
  evidence?: Evidence[];
  evidence_ready?: boolean;
  evidence_missing?: string[];
  evidence_demoted?: boolean;
  forced_downgrade?: boolean;
  judge_reasons?: JudgeReason[];
  citation_demoted?: boolean;
  persona_objections?: PersonaObjection[];
}

export interface Signal {
  id: string;
  source: string;
  source_name: string;
  title: string;
  pain_statement: string;
  observed_on: string;
  confidence: string;
  category: string | null;
  url: string | null;
}

export interface Overview {
  candidates: number;
  evaluated: number;
  verdicts: Record<Verdict, number>;
  factor_names: string[];
  last_generate: string | null;
  last_evaluate: string | null;
  judged_by_llm: boolean;
}

export interface Version {
  id: string;
  created_at: string;
  ui_count: number;
  en: number;
  zh: number;
}

// Founder profile (config/founder.json). Known editable fields are typed; extra
// metadata keys (_doc, _version, _labels, …) ride through untouched on save.
export interface FounderProfile {
  identity: string;
  capital_rmb: number;
  capital_note: string;
  skills: string[];
  network: string[];
  language_region_edge: string[];
  reach_keywords_en: string[];
  reach_keywords_zh: string[];
  hard_constraints: string[];
  anti_fit: string[];
  _labels?: Record<string, string>;
  [k: string]: unknown;
}

export type Backend = "rule" | "router" | "cc" | "mock";
export type JudgeBackend = "none" | "router" | "cc" | "mock";
export type SourceKey = "external_event" | "brain_inbox" | "pain_persona";

// pipeline-v2 §6 M6: read-only ledger views (data/ledger/*.jsonl).
export interface StageSurvival {
  survived: number;
  killed: number;
  rate: number;
}

export interface FunnelReport {
  stage_survival: Record<string, StageSurvival>;
  kill_reasons: Record<string, number>;
  verdict_distribution: Record<string, number>;
  outcomes: {
    count: number;
    avg_prediction_error: number | null;
    first_revenue_events: number;
    lessons: string[];
  };
}

export interface TraceEntry {
  entity_id: string;
  prompt_version: string;
  request: Record<string, unknown>;
  response: Record<string, unknown>;
  model: string;
  ts: string | null;
}

// ---- Studio v2: run-centric observability ----

export interface Usage {
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
}

export interface RunSummary {
  run_id: string;
  version_id: string | null;
  date: string;
  week: string;
  has_artifacts: boolean;
  stages: string[];
}

export interface StageFunnelRow {
  stage: string;
  entered: number;
  survived: number;
  killed: number;
  rate: number;
  kill_reasons: Record<string, number>;
  has_artifact: boolean;
}

export interface RunFunnel {
  run_id: string;
  week: string;
  date: string;
  stages: StageFunnelRow[];
  verdict_distribution: Record<string, number>;
  totals: { entered: number; survived_final: number };
}

export interface StageItem {
  id: string;
  event: "entered" | "survived" | "killed";
  killed_by: string | null;
  title: string;
  source: string;
  pain: string;
  alpha?: number | null;
  factors?: Factors;
  gate?: { ready: boolean; missing: string[] } | null;
}

export interface StageDrill {
  run_id: string;
  stage: string;
  entered: number;
  survived: number;
  killed: number;
  degraded: boolean;
  items: StageItem[];
}

export interface TraceRow {
  entity_id: string;
  prompt_version: string;
  request: { system?: string; user?: string };
  response: { text?: string; data?: Record<string, unknown>; ok?: boolean; error?: string };
  model: string;
  ts: string | null;
  usage?: Usage | null;
  cost?: number | null;
  latency_ms?: number | null;
}

export interface IdeaLineage {
  idea_id: string;
  run_id: string;
  signal: (Signal & { raw_text?: string; money_trace?: string }) | null;
  triage: { survived: boolean; killed_by: string | null } | null;
  candidate: Idea | null;
  generate: { survived: boolean; killed_by: string | null } | null;
  rank: { factors: Factors | null; alpha: number | null; decay: number | null; coarse_selected: boolean } | null;
  enrich: { evidence: Evidence[]; gate: { ready: boolean; missing: string[] } | null };
  diligence: Decision | null;
  traces: Record<string, TraceRow[]>;
  founder_labels: Record<string, unknown>[];
}

export interface RerunResult {
  run_id: string;
  week: string;
  stages: { stage: string; entered: number; survived: number; killed: number }[];
}

export interface AskResult {
  idea_id: string;
  run_id: string;
  question: string;
  answer: string;
  backend: string;
  usage: Usage | null;
  latency_ms: number | null;
  ts: string;
}

export type AskBackend = "router" | "mock";

export type WhatifBackend = "mock" | "router" | "dify";

export interface WhatifJudgeResult {
  idea_id: string;
  verdict: Verdict;
  eval_score: number;
  judged_by: "rule" | "llm";
  killer_objection: string;
  riskiest_assumption: string;
  judge_reasons: JudgeReason[];
}

// Compact feedback row (the full record with its frozen lineage stays on disk).
export interface FeedbackRow {
  feedback_id: string;
  ts: string;
  run_id: string;
  idea_id: string;
  labels: string[];
  note: string;
  system_verdict: Verdict | null;
  system_score: number | null;
  title: string | null;
}
