import type { Verdict } from "../types";
import { VERDICT_LABEL } from "../labels";

export function VerdictChip({ verdict }: { verdict: Verdict }) {
  return <span className={`chip ${verdict}`}>{VERDICT_LABEL[verdict] ?? verdict}</span>;
}

export function SyntheticChip() {
  return <span className="chip syn">模拟</span>;
}
