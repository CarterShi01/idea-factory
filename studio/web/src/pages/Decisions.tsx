import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Decision, Verdict, WhatifBackend, WhatifJudgeResult } from "../types";
import { VerdictChip } from "../components/VerdictChip";
import { VERDICT_LABEL } from "../labels";

const FILTERS: (Verdict | "all")[] = ["all", "pursue", "review", "kill"];
const FILTER_LABEL: Record<string, string> = { all: "全部", ...VERDICT_LABEL };
const WHATIF_BACKENDS: { key: WhatifBackend; label: string }[] = [
  { key: "mock", label: "模拟" },
  { key: "router", label: "腾讯" },
  { key: "dify", label: "Dify" },
];

function EvidenceList({ d }: { d: Decision }) {
  if (!d.evidence || d.evidence.length === 0) return null;
  return (
    <div className="kv">
      <b>钱的证据链：</b>
      {d.evidence.map((e) => (
        <div key={e.id} style={{ marginLeft: 12, fontSize: 12.5 }}>
          · [{e.kind}] {e.summary}
          {e.source_url && (
            <>
              {" "}
              <a href={e.source_url} target="_blank" rel="noreferrer">
                来源
              </a>
            </>
          )}
          {!e.valid && <span style={{ color: "var(--kill)" }}> ⚠️已过期</span>}
        </div>
      ))}
    </div>
  );
}

function JudgeReasons({ d }: { d: Decision }) {
  if (!d.judge_reasons || d.judge_reasons.length === 0) return null;
  return (
    <div className="kv">
      <b>裁决理由：</b>
      {d.judge_reasons.map((r, i) => (
        <div key={i} style={{ marginLeft: 12, fontSize: 12.5 }}>
          · {r.claim}
          {r.evidence_ids.length > 0 ? ` （证据：${r.evidence_ids.join(", ")}）` : " （无证据引用）"}
        </div>
      ))}
      {d.citation_demoted && (
        <div className="faint" style={{ marginLeft: 12 }}>⚠️ 该淘汰因未引用证据被自动打回复核</div>
      )}
    </div>
  );
}

function PersonaObjections({ d }: { d: Decision }) {
  if (!d.persona_objections || d.persona_objections.length === 0) return null;
  return (
    <div className="kv">
      <b>人群反对声（仅供参考）：</b>
      {d.persona_objections.map((o, i) => (
        <div key={i} style={{ marginLeft: 12, fontSize: 12.5 }}>
          · {o.persona}：{o.objection}
        </div>
      ))}
    </div>
  );
}

function WhatifPanel({ d }: { d: Decision }) {
  const [open, setOpen] = useState(false);
  const [solution, setSolution] = useState("");
  const [backend, setBackend] = useState<WhatifBackend>("mock");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<WhatifJudgeResult | null>(null);
  const [err, setErr] = useState("");

  async function run() {
    setBusy(true);
    setErr("");
    try {
      const r = await api.whatifJudge(d.idea_id, solution.trim() ? { solution: solution.trim() } : {}, backend);
      setResult(r);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ marginTop: 8 }}>
      <button className="btn ghost" style={{ fontSize: 12 }} onClick={() => setOpen((v) => !v)}>
        {open ? "收起 what-if" : "试一试（what-if，只重跑评审，不写入）"}
      </button>
      {open && (
        <div style={{ marginTop: 8, padding: 10, border: "1px solid var(--border, #333)", borderRadius: 8 }}>
          <div className="field">
            <label>覆盖「方案」文本（留空 = 用原文重跑）</label>
            <textarea
              className="txt"
              rows={2}
              style={{ width: "100%" }}
              value={solution}
              onChange={(e) => setSolution(e.target.value)}
            />
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <div className="seg">
              {WHATIF_BACKENDS.map((b) => (
                <button key={b.key} className={backend === b.key ? "on" : ""} onClick={() => setBackend(b.key)}>
                  {b.label}
                </button>
              ))}
            </div>
            <button className="btn" disabled={busy} onClick={run}>
              {busy ? <span className="spinner" /> : "重跑评审"}
            </button>
          </div>
          {err && <div className="empty" style={{ marginTop: 8 }}>{err}</div>}
          {result && (
            <div className="memo" style={{ marginTop: 10 }}>
              <div>
                <VerdictChip verdict={result.verdict} /> <span className="alpha mono">{result.eval_score.toFixed(0)}</span>
                {" "}（{result.judged_by === "llm" ? "LLM 评委" : "规则"}）
              </div>
              {result.killer_objection && <div className="kv"><b>最致命质疑：</b> {result.killer_objection}</div>}
              {result.judge_reasons.length > 0 && (
                <div className="kv">
                  <b>理由：</b>
                  {result.judge_reasons.map((r, i) => (
                    <div key={i} style={{ marginLeft: 12, fontSize: 12.5 }}>· {r.claim}</div>
                  ))}
                </div>
              )}
              <div className="faint" style={{ marginTop: 6 }}>仅预览，未写入 screened.json / ledger。</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function Decisions({ version }: { version?: string }) {
  const [rows, setRows] = useState<Decision[] | null>(null);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState<Verdict | "all">("all");
  const [labeled, setLabeled] = useState<Record<string, string>>({});

  useEffect(() => {
    api.decisions(version).then(setRows).catch((e) => setErr((e as Error).message));
  }, [version]);

  const shown = useMemo(
    () => (rows ?? []).filter((r) => filter === "all" || r.verdict === filter),
    [rows, filter],
  );

  async function label(ideaId: string, action: "star" | "kill") {
    try {
      await api.label(ideaId, action);
      setLabeled((cur) => ({ ...cur, [ideaId]: action }));
    } catch (e) {
      setErr((e as Error).message);
    }
  }

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
                <button
                  className="btn ghost"
                  style={{ fontSize: 12, padding: "3px 8px" }}
                  title="标星（写入 ledger 当标签）"
                  onClick={() => label(d.idea_id, "star")}
                >
                  {labeled[d.idea_id] === "star" ? "★" : "☆"}
                </button>
                <button
                  className="btn ghost"
                  style={{ fontSize: 12, padding: "3px 8px" }}
                  title="人工淘汰（写入 ledger 当标签）"
                  onClick={() => label(d.idea_id, "kill")}
                >
                  ✗
                </button>
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
            <EvidenceList d={d} />
            <JudgeReasons d={d} />
            <PersonaObjections d={d} />
            <div className="faint" style={{ fontSize: 12, marginTop: 8 }}>
              评审方式：{d.judged_by === "llm" ? "LLM 评委" : "规则"}
              {d.killed_by.length ? ` · 致命短板：${d.killed_by.join("、")}` : ""}
              {d.risk_flags.length ? ` · ${d.risk_flags.length} 项风险提示` : ""}
              {d.evidence_ready === false && d.evidence_missing?.length ? ` · 待补证据：${d.evidence_missing.join("、")}` : ""}
            </div>
            <WhatifPanel d={d} />
          </div>
        ))}
      </div>
    </>
  );
}
