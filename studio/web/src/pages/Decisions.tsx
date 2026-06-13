import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Decision, Verdict } from "../types";
import { VerdictChip } from "../components/VerdictChip";
import { VERDICT_LABEL } from "../labels";

const FILTERS: (Verdict | "all")[] = ["all", "pursue", "review", "kill"];
const FILTER_LABEL: Record<string, string> = { all: "全部", ...VERDICT_LABEL };

export function Decisions() {
  const [rows, setRows] = useState<Decision[] | null>(null);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState<Verdict | "all">("all");

  useEffect(() => {
    api.decisions().then(setRows).catch((e) => setErr((e as Error).message));
  }, []);

  const shown = useMemo(
    () => (rows ?? []).filter((r) => filter === "all" || r.verdict === filter),
    [rows, filter],
  );

  if (err) return <div className="empty">{err}</div>;
  if (!rows) return <div className="empty"><span className="spinner" /> 加载中…</div>;
  if (!rows.length) return <div className="empty">还没有评估结果 —— 先运行“评估”阶段。</div>;

  return (
    <>
      <div className="topbar">
        <div>
          <h1>评估决策</h1>
          <div className="sub">淘汰闸 + 评分。每条幸存创意都附一条最致命质疑和一个廉价验证实验。</div>
        </div>
        <div className="seg">
          {FILTERS.map((f) => (
            <button key={f} className={filter === f ? "on" : ""} onClick={() => setFilter(f)}>
              {FILTER_LABEL[f]}
            </button>
          ))}
        </div>
      </div>

      <div className="grid" style={{ gap: 12 }}>
        {shown.map((d) => (
          <div className="card" key={d.idea_id}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", gap: 12 }}>
              <div style={{ fontWeight: 650, fontSize: 15 }}>{d.title}</div>
              <div style={{ display: "flex", gap: 8, alignItems: "center", whiteSpace: "nowrap" }}>
                <span className="alpha mono">{d.eval_score.toFixed(0)}</span>
                <VerdictChip verdict={d.verdict} />
              </div>
            </div>
            {d.killer_objection && (
              <div className="memo" style={{ marginTop: 10 }}>
                <span className="obj">⚑ {d.killer_objection}</span>
              </div>
            )}
            <div className="kv"><b>最危险假设：</b> {d.riskiest_assumption}</div>
            <div className="kv"><span className="rat">▷ 最小验证：</span> {d.cheap_experiment}</div>
            <div className="faint" style={{ fontSize: 12, marginTop: 8 }}>
              评审方式：{d.judged_by === "llm" ? "LLM 评委" : "规则"}
              {d.killed_by.length ? ` · 致命短板：${d.killed_by.join("、")}` : ""}
              {d.risk_flags.length ? ` · ${d.risk_flags.length} 项风险提示` : ""}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
