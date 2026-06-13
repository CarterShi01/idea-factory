import { useState } from "react";
import { api } from "../api";
import type { Backend, JudgeBackend, SourceKey } from "../types";

const GEN_BACKENDS: { key: Backend; label: string }[] = [
  { key: "rule", label: "规则" },
  { key: "router", label: "腾讯" },
  { key: "cc", label: "CC 手动" },
  { key: "mock", label: "模拟" },
];
const JUDGE_BACKENDS: { key: JudgeBackend; label: string }[] = [
  { key: "none", label: "纯规则" },
  { key: "router", label: "腾讯" },
  { key: "cc", label: "CC 手动" },
  { key: "mock", label: "模拟" },
];
const PERSONA_BACKENDS: { key: string; label: string }[] = [
  { key: "static", label: "静态" },
  { key: "router", label: "腾讯" },
  { key: "cc", label: "CC 手动" },
  { key: "mock", label: "模拟" },
];
const SOURCES: { key: SourceKey; label: string }[] = [
  { key: "external_event", label: "外部事件" },
  { key: "brain_inbox", label: "收件箱" },
  { key: "pain_persona", label: "模拟痛点" },
];

function Seg<T extends string>({
  opts,
  val,
  onChange,
}: {
  opts: { key: T; label: string }[];
  val: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="seg">
      {opts.map((o) => (
        <button key={o.key} className={val === o.key ? "on" : ""} onClick={() => onChange(o.key)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function RunPanel({ onRan }: { onRan: () => void }) {
  const [gb, setGb] = useState<Backend>("rule");
  const [srcs, setSrcs] = useState<SourceKey[]>([]);
  const [topN, setTopN] = useState(15);
  const [live, setLive] = useState(false);
  const [dyn, setDyn] = useState(false);
  const [pb, setPb] = useState("static");
  const [jb, setJb] = useState<JudgeBackend>("none");
  const [floor, setFloor] = useState(0.25);
  const [idea, setIdea] = useState("");
  const [log, setLog] = useState("");
  const [busy, setBusy] = useState<"" | "gen" | "eval" | "inbox">("");

  function toggleSrc(s: SourceKey) {
    setSrcs((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]));
  }

  async function gen() {
    setBusy("gen");
    setLog("正在生成…");
    try {
      const r = await api.generate({
        backend: gb,
        sources: srcs.length ? srcs : null,
        top_n: topN,
        live,
        use_state: dyn,
        persona_backend: pb,
      });
      setLog(`✓ 生成完成 → ${r.raw_count} 原始 → ${r.signal_count} 信号 → ${r.deduped_count} 去重后 → ${r.candidate_count} 候选`);
      onRan();
    } catch (e) {
      setLog(`✗ ${(e as Error).message}`);
    } finally {
      setBusy("");
    }
  }

  async function evaluate() {
    setBusy("eval");
    setLog("正在评估…");
    try {
      const r = await api.evaluate({ backend: jb, floor, top_n: 20 });
      setLog(`✓ 评估完成 → 共 ${r.evaluated} · 推进 ${r.pursue} · 待验证 ${r.review} · 淘汰 ${r.killed}`);
      onRan();
    } catch (e) {
      setLog(`✗ ${(e as Error).message}`);
    } finally {
      setBusy("");
    }
  }

  async function addIdea() {
    if (!idea.trim()) return;
    setBusy("inbox");
    try {
      await api.inbox({ title: idea.trim() });
      setLog(`✓ 已记入灵感收件箱：${idea.trim()}`);
      setIdea("");
    } catch (e) {
      setLog(`✗ ${(e as Error).message}`);
    } finally {
      setBusy("");
    }
  }

  return (
    <>
      <div className="topbar">
        <div>
          <h1>运行管线</h1>
          <div className="sub">触发生成与评估。腾讯 = 自动调用；CC 手动 = 写请求包交人工处理；动态 = 记历史、只取增量。</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 18 }}>
        <h3>源② · 记一条灵感</h3>
        <div style={{ display: "flex", gap: 10 }}>
          <input
            className="txt"
            placeholder="随手记下一个念头，回车或点按钮"
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addIdea()}
          />
          <button className="btn ghost" disabled={!!busy} onClick={addIdea} style={{ whiteSpace: "nowrap" }}>
            {busy === "inbox" ? <span className="spinner" /> : "记一条"}
          </button>
        </div>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h3>A · 生成</h3>
          <div className="field">
            <label>后端</label>
            <Seg opts={GEN_BACKENDS} val={gb} onChange={setGb} />
          </div>
          <div className="field">
            <label>来源 {srcs.length === 0 && <span className="faint">（全部）</span>}</label>
            <div className="seg">
              {SOURCES.map((s) => (
                <button key={s.key} className={srcs.includes(s.key) ? "on" : ""} onClick={() => toggleSrc(s.key)}>
                  {s.label}
                </button>
              ))}
            </div>
          </div>
          <div className="field">
            <label>源③ 痛点合成（人群×痛点）</label>
            <Seg opts={PERSONA_BACKENDS} val={pb} onChange={setPb} />
          </div>
          <div className="field" style={{ display: "flex", gap: 18 }}>
            <label style={{ cursor: "pointer" }}>
              <input type="checkbox" checked={live} onChange={(e) => setLive(e.target.checked)} /> 实时抓取（联网）
            </label>
            <label style={{ cursor: "pointer" }}>
              <input type="checkbox" checked={dyn} onChange={(e) => setDyn(e.target.checked)} /> 动态状态（去重+趋势）
            </label>
          </div>
          <div className="field">
            <label>报告条数</label>
            <input className="txt" type="number" value={topN} onChange={(e) => setTopN(+e.target.value)} />
          </div>
          <button className="btn" disabled={!!busy} onClick={gen}>
            {busy === "gen" ? <span className="spinner" /> : "运行生成"}
          </button>
        </div>

        <div className="card">
          <h3>B · 评估</h3>
          <div className="field">
            <label>评委后端</label>
            <Seg opts={JUDGE_BACKENDS} val={jb} onChange={setJb} />
          </div>
          <div className="field">
            <label>淘汰闸阈值（{floor.toFixed(2)}）</label>
            <input
              className="txt"
              type="range"
              min={0}
              max={0.6}
              step={0.05}
              value={floor}
              onChange={(e) => setFloor(+e.target.value)}
            />
          </div>
          <div className="muted-note" style={{ marginBottom: 14 }}>
            LLM 评委只评估过了淘汰闸的幸存者（省 token）。<b>CC 手动</b> 会写出请求包并暂停，交人工在 Claude Code 里处理。
          </div>
          <button className="btn" disabled={!!busy} onClick={evaluate}>
            {busy === "eval" ? <span className="spinner" /> : "运行评估"}
          </button>
        </div>
      </div>

      <div className="card" style={{ marginTop: 18 }}>
        <h3>结果</h3>
        <div className="runlog">{log || "—"}</div>
      </div>
    </>
  );
}
