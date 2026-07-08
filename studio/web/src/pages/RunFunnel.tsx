import { useEffect, useState } from "react";
import { api } from "../api";
import type { RunFunnel as RunFunnelData } from "../types";
import { FunnelBar } from "../components/FunnelBar";
import { navigate } from "../hooks/useHashRoute";
import { VerdictChip } from "../components/VerdictChip";

/** Home: one run's 8-stage funnel. Click a stage to drill into its items. */
export function RunFunnel({ runId }: { runId: string }) {
  const [data, setData] = useState<RunFunnelData | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    setData(null);
    setErr("");
    api.run(runId).then(setData).catch((e) => setErr((e as Error).message));
  }, [runId]);

  if (err) return <div className="empty">{err}</div>;
  if (!data) return <div className="empty"><span className="spinner" /> 加载运行…</div>;
  if (!data.stages.length) return <div className="empty">这个运行没有分段数据。</div>;

  const maxEntered = Math.max(...data.stages.map((s) => s.entered), 1);
  const vd = data.verdict_distribution;

  return (
    <>
      <div className="topbar">
        <div>
          <h1>漏斗 · {runId}</h1>
          <div className="sub">
            {data.week} · {data.date} — 点任一段钻进去看它处理了哪些条目、每条为什么被杀
          </div>
        </div>
        <div className="verdict-tally">
          <VerdictChip verdict="pursue" /> <span className="mono">{vd.pursue ?? 0}</span>
          <VerdictChip verdict="review" /> <span className="mono">{vd.review ?? 0}</span>
          <VerdictChip verdict="kill" /> <span className="mono">{vd.kill ?? 0}</span>
        </div>
      </div>

      <div className="card funnel">
        {data.stages.map((row) => (
          <FunnelBar
            key={row.stage}
            row={row}
            maxEntered={maxEntered}
            onClick={() => navigate({ name: "stage", runId, stage: row.stage })}
          />
        ))}
      </div>
      <div className="funnel-legend faint">
        条形长度 = 相对入量；实心 = 存活。杀因 chip 标在每段右侧。成本梯度随
        <span className="mono"> LLM 段</span> 出现在钻取与血统里（token/¥/ms）。
      </div>
    </>
  );
}
