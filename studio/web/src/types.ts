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
