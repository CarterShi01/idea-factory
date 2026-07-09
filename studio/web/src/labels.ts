// 中文显示标签：内部 key 保持英文（标识符 / 与内核契约一致），仅 UI 展示用中文。

import type { Verdict } from "./types";

export const FACTOR_LABEL: Record<string, string> = {
  market_freshness: "市场新鲜度",
  pain_intensity: "痛点强度",
  build_cost: "可落地性",
  moat_signal: "护城河",
  competition_density: "竞争稀缺度",
  distribution_fit: "触达匹配度",
  payment_signal: "付费信号",
};

export const VERDICT_LABEL: Record<Verdict, string> = {
  pursue: "推进",
  review: "待验证",
  kill: "淘汰",
};

export const SOURCE_LABEL: Record<string, string> = {
  external_event: "外部事件",
  brain_inbox: "灵感收件箱",
  pain_persona: "模拟痛点",
};

// 八段名 + 段序号(前端漏斗展示)。
export const STAGE_LABEL: Record<string, string> = {
  recall: "召回",
  triage: "硬杀",
  generate: "生成",
  rank: "粗排",
  enrich: "取证",
  diligence: "裁决",
  portfolio: "组合",
  retro: "复盘",
};
export const STAGE_NUM: Record<string, string> = {
  recall: "①", triage: "②", generate: "③", rank: "④",
  enrich: "⑤", diligence: "⑥", portfolio: "⑦", retro: "⑧",
};
export const STAGE_MISSION: Record<string, string> = {
  recall: "从钱在流动的地方捞信号",
  triage: "便宜地硬杀（去重 + >24月过期）",
  generate: "信号→成型候选（禁模板套话）",
  rank: "纯代码因子加权，决定谁进昂贵半场",
  enrich: "给幸存者配齐钱证据链，过证据门",
  diligence: "拿证据开庭：批判→裁决→强制纪律",
  portfolio: "组合成周报 Top≤3 + 48h 测试包",
  retro: "预测 vs 实际，让系统随时间变准",
};

// 杀因中文（跨段汇总）。
export const KILL_REASON_LABEL: Record<string, string> = {
  stale_24m: "信号超 24 月过期",
  seen_before: "跨日已见过",
  exact_or_near_dup: "精确/近重去重",
  profile_mismatch: "画像 anti-fit",
  ranked_out: "粗排截断",
  eval_kill: "裁决淘汰",
  pain_intensity: "痛点证据太弱",
  build_cost: "一人做不了",
  awaiting_evidence: "待补证据",
  unknown: "未记原因",
};

// 证据门缺项中文。
export const GATE_MISSING_LABEL: Record<string, string> = {
  paying_proof: "付费证据",
  competitor_pricing: "竞品定价",
  reach_path: "触达路径",
};

// 反馈标签(问题定位型):每个标签直接对应漏斗的一个失败点,方便日后在 CC 里
// 按标签聚合、定位该修哪段/哪个 prompt。other 由 note 自由文本承载,不在此列。
export const FEEDBACK_LABELS: { id: string; zh: string; hint: string }[] = [
  { id: "wrong_kill", zh: "错杀", hint: "系统 KILL 了但我看好 → judge/gate 过严" },
  { id: "wrong_pursue", zh: "错捧", hint: "系统 PURSUE/REVIEW 但我否 → judge 过松" },
  { id: "bad_signal", zh: "信号噪音", hint: "信号本身无关/是噪音 → recall 源质量" },
  { id: "fake_pain", zh: "伪痛点", hint: "痛点臆想/伪需求 → generate / pain 因子" },
  { id: "weak_evidence", zh: "证据牵强", hint: "证据不对/牵强 → enrich 取证" },
  { id: "off_profile", zh: "不符画像", hint: "不符我的方向/独占 → founder.json / anti-fit" },
  { id: "good_catch", zh: "判对了", hint: "系统判对，值得记住(正样本)" },
];
export const feedbackLabelZh = (id: string) =>
  FEEDBACK_LABELS.find((l) => l.id === id)?.zh ?? id;

export const factorLabel = (k: string) => FACTOR_LABEL[k] ?? k;
export const sourceLabel = (k: string) => SOURCE_LABEL[k] ?? k;
export const stageLabel = (k: string) => STAGE_LABEL[k] ?? k;
export const killReasonLabel = (k: string) => KILL_REASON_LABEL[k] ?? k;
export const gateMissingLabel = (k: string) => GATE_MISSING_LABEL[k] ?? k;
