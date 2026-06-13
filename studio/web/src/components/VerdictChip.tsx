import type { Verdict } from "../types";

const LABEL: Record<Verdict, string> = { pursue: "pursue", review: "review", kill: "kill" };

export function VerdictChip({ verdict }: { verdict: Verdict }) {
  return <span className={`chip ${verdict}`}>{LABEL[verdict] ?? verdict}</span>;
}

export function SyntheticChip() {
  return <span className="chip syn">synthetic</span>;
}
