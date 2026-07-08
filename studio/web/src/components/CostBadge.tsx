import type { Usage } from "../types";

/** tokens · ¥cost · latency — null-safe. Renders "离线/规则" when no usage
 *  (offline/rule path spends no tokens, so there's nothing to show). */
export function CostBadge({
  usage,
  cost,
  latencyMs,
}: {
  usage?: Usage | null;
  cost?: number | null;
  latencyMs?: number | null;
}) {
  if (!usage && cost == null && latencyMs == null) {
    return <span className="cost-badge dim">离线 · 0 token</span>;
  }
  const tok = usage?.total_tokens;
  return (
    <span className="cost-badge">
      {tok != null && <span className="mono">{tok} tok</span>}
      {cost != null ? <span className="mono">¥{cost.toFixed(4)}</span> : <span className="faint">未计价</span>}
      {latencyMs != null && <span className="mono faint">{latencyMs.toFixed(0)}ms</span>}
    </span>
  );
}
