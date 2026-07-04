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
