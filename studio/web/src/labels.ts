// 中文显示标签：内部 key 保持英文（标识符 / 与内核契约一致），仅 UI 展示用中文。

import type { Verdict } from "./types";

export const FACTOR_LABEL: Record<string, string> = {
  market_freshness: "市场新鲜度",
  pain_intensity: "痛点强度",
  build_cost: "可落地性",
  moat_signal: "护城河",
  competition_density: "竞争稀缺度",
  distribution_fit: "触达匹配度",
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

export const factorLabel = (k: string) => FACTOR_LABEL[k] ?? k;
export const sourceLabel = (k: string) => SOURCE_LABEL[k] ?? k;
