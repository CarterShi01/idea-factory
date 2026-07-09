import { useEffect, useState, type ReactNode } from "react";
import { api } from "../api";
import type { IdeaLineage as Lineage, WhatifBackend, WhatifJudgeResult } from "../types";
import { FactorBars } from "../components/FactorBar";
import { VerdictChip } from "../components/VerdictChip";
import { TracePane } from "../components/TracePane";
import { AskPanel } from "../components/AskPanel";
import { FeedbackPanel } from "../components/FeedbackPanel";
import { STAGE_NUM, stageLabel, killReasonLabel, gateMissingLabel } from "../labels";

/** The T6.2 view: one idea's full cross-stage journey as a vertical timeline,
 *  each LLM step showing its verbatim prompt+response+cost, plus label / what-if
 *  / real-time ask. "看这条为什么被 pass" answerable in 30s. */
export function IdeaLineage({ runId, ideaId }: { runId: string; ideaId: string }) {
  const [lin, setLin] = useState<Lineage | null>(null);
  const [err, setErr] = useState("");
  const [labeled, setLabeled] = useState("");

  useEffect(() => {
    setLin(null);
    api.ideaLineage(runId, ideaId).then(setLin).catch((e) => setErr((e as Error).message));
  }, [runId, ideaId]);

  async function label(action: "star" | "kill") {
    try {
      await api.label(ideaId, action, { run_id: runId });
      setLabeled(action);
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  if (err) return <div className="empty">{err}</div>;
  if (!lin) return <div className="empty"><span className="spinner" /> 组装血统…</div>;

  const c = lin.candidate;
  const d = lin.diligence;
  const sig = lin.signal;

  return (
    <>
      <div className="topbar">
        <div>
          <a className="crumb" href={`#/run/${encodeURIComponent(runId)}`}>← 漏斗</a>
          <h1>{c?.title || ideaId}</h1>
          <div className="sub mono faint">{ideaId} · {runId}</div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {d && <><span className="alpha mono">{d.eval_score.toFixed(0)}</span><VerdictChip verdict={d.verdict} /></>}
          <button className="btn ghost" title="标星，写入 ledger 当标签" onClick={() => label("star")}>
            {labeled === "star" ? "★" : "☆"}
          </button>
          <button className="btn ghost" title="人工淘汰，写入 ledger 当标签" onClick={() => label("kill")}>✗</button>
        </div>
      </div>

      <div className="lineage">
        {/* ① recall */}
        <Step num="recall" title="召回信号">
          {sig ? (
            <div className="kv">
              <div><b>[{sig.source_name || sig.source}]</b> {sig.title}　<span className="faint mono">{sig.observed_on}</span></div>
              {sig.raw_text && <div className="quote">{sig.raw_text}</div>}
              {sig.money_trace && <div className="kv"><b>钱的痕迹：</b>{sig.money_trace}</div>}
            </div>
          ) : <Faded>无来源信号（可能是灵感 inbox / 融合候选）</Faded>}
        </Step>

        {/* ② triage */}
        <Step num="triage" title="硬杀" verdict={lin.triage}>
          {lin.triage?.survived ? <Ok>通过硬红线</Ok>
            : lin.triage ? <Bad>被杀：{killReasonLabel(lin.triage.killed_by || "")}</Bad>
            : <Faded>无记录</Faded>}
        </Step>

        {/* ③ generate */}
        <Step num="generate" title="生成候选" verdict={lin.generate}>
          {c ? (
            <div className="kv">
              <div><b>方案：</b>{c.solution}</div>
              {c.mechanism && <div><b>机制：</b>{c.mechanism}</div>}
              {c.why_now && <div><b>为何现在：</b>{c.why_now}</div>}
              {c.first_10_customers && <div><b>前10客户：</b>{c.first_10_customers}</div>}
              {lin.generate && !lin.generate.survived && <Bad>被杀：{killReasonLabel(lin.generate.killed_by || "")}</Bad>}
            </div>
          ) : <Faded>无候选</Faded>}
          {lin.traces.generate && <TracePane label="生成 LLM" rows={lin.traces.generate} />}
        </Step>

        {/* ④ rank */}
        <Step num="rank" title="粗排打分">
          {lin.rank ? (
            <>
              <div className="kv">
                <span className="alpha mono">alpha {lin.rank.alpha?.toFixed(4)}</span>
                <span className="faint mono"> · 衰减 {lin.rank.decay?.toFixed(3)}</span>
                {" "}{lin.rank.coarse_selected ? <Ok>进入昂贵半场</Ok> : <Bad>粗排截断，未进昂贵半场</Bad>}
              </div>
              {lin.rank.factors && <FactorBars factors={lin.rank.factors} />}
            </>
          ) : <Faded>无打分</Faded>}
        </Step>

        {/* ⑤ enrich */}
        <Step num="enrich" title="取证 · 证据门">
          {lin.enrich.gate ? (
            lin.enrich.gate.ready
              ? <Ok>证据门通过</Ok>
              : <Bad>证据门未过 —— 缺 {lin.enrich.gate.missing.map(gateMissingLabel).join("、")}</Bad>
          ) : <Faded>未跑证据门</Faded>}
          {lin.enrich.evidence.length > 0 && (
            <div className="kv" style={{ marginTop: 6 }}>
              <b>钱的证据链：</b>
              {lin.enrich.evidence.map((e) => (
                <div key={e.id} className="ev-row">
                  · [{e.kind}] {e.summary}
                  {e.source_url && <> <a href={e.source_url} target="_blank" rel="noreferrer">来源</a></>}
                  {!e.valid && <span style={{ color: "var(--kill)" }}> ⚠️已过期</span>}
                </div>
              ))}
            </div>
          )}
        </Step>

        {/* ⑥ diligence */}
        <Step num="diligence" title="裁决" verdict={d ? { survived: d.verdict !== "kill", killed_by: null } : null}>
          {d ? (
            <>
              {d.killer_objection && <div className="memo"><span className="obj">⚑ {d.killer_objection}</span></div>}
              <div className="kv"><b>最危险假设：</b>{d.riskiest_assumption}</div>
              <div className="kv"><span className="rat">▷ 最小验证：</span>{d.cheap_experiment}</div>
              {d.judge_reasons && d.judge_reasons.length > 0 && (
                <div className="kv"><b>裁决理由：</b>
                  {d.judge_reasons.map((r, i) => (
                    <div key={i} className="ev-row">· {r.claim}
                      {r.evidence_ids.length ? `（证据：${r.evidence_ids.join(", ")}）` : "（无证据引用）"}</div>
                  ))}
                  {d.citation_demoted && <div className="faint">⚠️ 淘汰因未引证被自动打回复核</div>}
                </div>
              )}
              {d.persona_objections && d.persona_objections.length > 0 && (
                <div className="kv"><b>人群反对声（仅供参考）：</b>
                  {d.persona_objections.map((o, i) => <div key={i} className="ev-row">· {o.persona}：{o.objection}</div>)}
                </div>
              )}
              {d.risk_flags && d.risk_flags.length > 0 && (
                <div className="kv faint">风险提示：{d.risk_flags.join("；")}</div>
              )}
              <div className="faint" style={{ fontSize: 12, marginTop: 4 }}>
                评审方式：{d.judged_by === "llm" ? "LLM 评委" : "规则前闸"}
                {d.killed_by.length ? ` · 致命短板：${d.killed_by.map(killReasonLabel).join("、")}` : ""}
              </div>
            </>
          ) : <Faded>未进入裁决（更早被杀）</Faded>}
          {lin.traces.critique && <TracePane label="对抗批判 critique" rows={lin.traces.critique} />}
          {lin.traces.diligence && <TracePane label="评委 judge" rows={lin.traces.diligence} />}
          {lin.traces.ask && <TracePane label="历史追问 ask" rows={lin.traces.ask} />}
        </Step>
      </div>

      <div className="grid cols-2" style={{ marginTop: 18 }}>
        <div className="card"><WhatifPanel ideaId={ideaId} /></div>
        <div className="card"><AskPanel runId={runId} ideaId={ideaId} /></div>
      </div>
      <div className="card" style={{ marginTop: 18 }}>
        <FeedbackPanel runId={runId} ideaId={ideaId} />
      </div>
    </>
  );
}

function Step({ num, title, verdict, children }: {
  num: string; title: string;
  verdict?: { survived: boolean; killed_by: string | null } | null;
  children: ReactNode;
}) {
  const dead = verdict && !verdict.survived;
  return (
    <div className={`lstep ${dead ? "dead" : ""}`}>
      <div className="lstep-rail"><span className="lstep-num">{STAGE_NUM[num]}</span></div>
      <div className="lstep-body">
        <div className="lstep-title">{stageLabel(num)} · {title}</div>
        <div className="lstep-content">{children}</div>
      </div>
    </div>
  );
}

const Ok = ({ children }: { children: ReactNode }) => <span className="tag ok">{children}</span>;
const Bad = ({ children }: { children: ReactNode }) => <span className="tag bad">{children}</span>;
const Faded = ({ children }: { children: ReactNode }) => <span className="faint">{children}</span>;

function WhatifPanel({ ideaId }: { ideaId: string }) {
  const [solution, setSolution] = useState("");
  const [backend, setBackend] = useState<WhatifBackend>("mock");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<WhatifJudgeResult | null>(null);
  const [err, setErr] = useState("");
  const BACKENDS: { key: WhatifBackend; label: string }[] = [
    { key: "mock", label: "模拟" }, { key: "router", label: "腾讯" }, { key: "dify", label: "Dify" },
  ];
  async function run() {
    setBusy(true); setErr("");
    try {
      setResult(await api.whatifJudge(ideaId, solution.trim() ? { solution: solution.trim() } : {}, backend));
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  return (
    <div>
      <b>What-if · 重跑评审（不写入）</b>
      <div className="field" style={{ marginTop: 8 }}>
        <label>覆盖「方案」文本（留空 = 用原文重跑）</label>
        <textarea className="txt" rows={2} value={solution} onChange={(e) => setSolution(e.target.value)} />
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <div className="seg tiny">
          {BACKENDS.map((b) => (
            <button key={b.key} className={backend === b.key ? "on" : ""} onClick={() => setBackend(b.key)}>{b.label}</button>
          ))}
        </div>
        <button className="btn" disabled={busy} onClick={run}>{busy ? <span className="spinner" /> : "重跑"}</button>
      </div>
      {err && <div className="err">{err}</div>}
      {result && (
        <div className="memo" style={{ marginTop: 10 }}>
          <div><VerdictChip verdict={result.verdict} /> <span className="alpha mono">{result.eval_score.toFixed(0)}</span>
            {" "}（{result.judged_by === "llm" ? "LLM 评委" : "规则"}）</div>
          {result.killer_objection && <div className="kv"><b>最致命质疑：</b>{result.killer_objection}</div>}
          <div className="faint" style={{ marginTop: 6 }}>仅预览，未写入 screened.json / ledger。</div>
        </div>
      )}
    </div>
  );
}
