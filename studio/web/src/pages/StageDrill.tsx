import { useEffect, useState } from "react";
import { api } from "../api";
import type { StageDrill as StageDrillData } from "../types";
import { navigate } from "../hooks/useHashRoute";
import { STAGE_NUM, STAGE_MISSION, stageLabel, killReasonLabel, gateMissingLabel } from "../labels";

/** Drill into one stage: which items survived, which died and WHY. Rerun the
 *  stage (destructive) from here. Click an item → its full lineage. */
export function StageDrill({ runId, stage }: { runId: string; stage: string }) {
  const [data, setData] = useState<StageDrillData | null>(null);
  const [err, setErr] = useState("");
  const [show, setShow] = useState<"all" | "survived" | "killed">("all");
  const [rerunMsg, setRerunMsg] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    setData(null);
    api.stageDrill(runId, stage).then(setData).catch((e) => setErr((e as Error).message));
  }
  useEffect(load, [runId, stage]);

  async function rerun() {
    if (!confirm(`重跑「${stageLabel(stage)}」段？\n这会覆盖 ${stage} 的工件并追加 ledger；下游各段工件会变过期，需要一并重跑。`)) return;
    setBusy(true);
    setRerunMsg("");
    try {
      const backends = stage === "diligence" ? { judge_backend: "none" } : {};
      const r = await api.rerunStage({ stage, ...backends });
      setRerunMsg(`已重跑 ${r.stages.map((s) => `${stageLabel(s.stage)} ${s.entered}→${s.survived}`).join("、")}`);
      load();
    } catch (e) {
      setRerunMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (err) return <div className="empty">{err}</div>;
  if (!data) return <div className="empty"><span className="spinner" /> 加载段…</div>;

  const items = data.items.filter((i) => show === "all" || i.event === show);

  return (
    <>
      <div className="topbar">
        <div>
          <a className="crumb" href={`#/run/${encodeURIComponent(runId)}`}>← 漏斗</a>
          <h1>{STAGE_NUM[stage]} {stageLabel(stage)} 段</h1>
          <div className="sub">
            {STAGE_MISSION[stage]} · 入 {data.entered} → 存活 {data.survived} · 杀 {data.killed}
            {data.degraded && <span style={{ color: "var(--review)" }}>（历史运行无工件，仅日志字段）</span>}
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <div className="seg">
            {(["all", "survived", "killed"] as const).map((k) => (
              <button key={k} className={show === k ? "on" : ""} onClick={() => setShow(k)}>
                {k === "all" ? "全部" : k === "survived" ? "存活" : "被杀"}
              </button>
            ))}
          </div>
          <button className="btn ghost" onClick={rerun} disabled={busy} title="破坏性：覆盖本段工件 + 追加 ledger">
            {busy ? <span className="spinner" /> : "重跑本段"}
          </button>
        </div>
      </div>
      {rerunMsg && <div className="runlog" style={{ marginBottom: 14 }}>{rerunMsg}</div>}

      <div className="drill-list">
        {items.map((it) => (
          <button
            key={it.id + it.event}
            className={`drill-item ${it.event}`}
            onClick={() => navigate({ name: "idea", runId, ideaId: it.id })}
          >
            <span className={`dot ${it.event}`} />
            <span className="drill-title">{it.title || it.pain || it.id}</span>
            <span className="drill-meta">
              {it.alpha != null && <span className="alpha mono">α{it.alpha.toFixed(3)}</span>}
              {it.gate && !it.gate.ready && (
                <span className="reason-chip">缺 {it.gate.missing.map(gateMissingLabel).join("、")}</span>
              )}
              {it.event === "killed" && it.killed_by && (
                <span className="reason-chip kill">{killReasonLabel(it.killed_by)}</span>
              )}
            </span>
            <span className="mono faint drill-id">{it.id}</span>
          </button>
        ))}
        {!items.length && <div className="empty">没有符合筛选的条目。</div>}
      </div>
    </>
  );
}
