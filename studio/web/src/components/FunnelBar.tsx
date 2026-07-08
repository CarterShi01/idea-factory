import type { StageFunnelRow } from "../types";
import { STAGE_NUM, STAGE_MISSION, stageLabel, killReasonLabel } from "../labels";

/** One stage row of the run funnel: 进→存活, 杀数, a survival bar, kill reasons.
 *  Pure CSS bar (no chart lib). Width of the bar = survival rate. */
export function FunnelBar({
  row,
  maxEntered,
  onClick,
}: {
  row: StageFunnelRow;
  maxEntered: number;
  onClick?: () => void;
}) {
  const enteredPct = maxEntered ? (row.entered / maxEntered) * 100 : 0;
  const survivedPct = maxEntered ? (row.survived / maxEntered) * 100 : 0;
  const reasons = Object.entries(row.kill_reasons).sort((a, b) => b[1] - a[1]);
  return (
    <button className="funnel-row" onClick={onClick} title={STAGE_MISSION[row.stage]}>
      <span className="funnel-head">
        <span className="funnel-num">{STAGE_NUM[row.stage] ?? ""}</span>
        <span className="funnel-name">{stageLabel(row.stage)}</span>
      </span>
      <span className="funnel-nums mono">
        {row.entered} <span className="faint">→</span> {row.survived}
        {row.killed > 0 && <span className="funnel-kill"> 杀{row.killed}</span>}
      </span>
      <span className="funnel-track" aria-hidden>
        <span className="funnel-entered" style={{ width: `${enteredPct}%` }} />
        <span className="funnel-survived" style={{ width: `${survivedPct}%` }} />
      </span>
      <span className="funnel-rate mono">{(row.rate * 100).toFixed(0)}%</span>
      <span className="funnel-reasons">
        {reasons.map(([r, n]) => (
          <span className="reason-chip" key={r}>{killReasonLabel(r)} {n}</span>
        ))}
      </span>
    </button>
  );
}
