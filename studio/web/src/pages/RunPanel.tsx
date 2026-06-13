import { useState } from "react";
import { api } from "../api";
import type { Backend, JudgeBackend, SourceKey } from "../types";

const GEN_BACKENDS: Backend[] = ["rule", "router", "cc", "mock"];
const JUDGE_BACKENDS: JudgeBackend[] = ["none", "router", "cc", "mock"];
const SOURCES: { key: SourceKey; label: string }[] = [
  { key: "external_event", label: "External" },
  { key: "brain_inbox", label: "Inbox" },
  { key: "pain_persona", label: "Persona" },
];

function Seg<T extends string>({ opts, val, onChange }: { opts: T[]; val: T; onChange: (v: T) => void }) {
  return (
    <div className="seg">
      {opts.map((o) => (
        <button key={o} className={val === o ? "on" : ""} onClick={() => onChange(o)}>
          {o}
        </button>
      ))}
    </div>
  );
}

export function RunPanel({ onRan }: { onRan: () => void }) {
  const [gb, setGb] = useState<Backend>("rule");
  const [srcs, setSrcs] = useState<SourceKey[]>([]);
  const [topN, setTopN] = useState(15);
  const [jb, setJb] = useState<JudgeBackend>("none");
  const [floor, setFloor] = useState(0.25);
  const [log, setLog] = useState("");
  const [busy, setBusy] = useState<"" | "gen" | "eval">("");

  function toggleSrc(s: SourceKey) {
    setSrcs((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]));
  }

  async function gen() {
    setBusy("gen");
    setLog("running generate…");
    try {
      const r = await api.generate({ backend: gb, sources: srcs.length ? srcs : null, top_n: topN });
      setLog(`✓ generate → ${r.raw_count} raw → ${r.signal_count} signals → ${r.deduped_count} deduped → ${r.candidate_count} candidates`);
      onRan();
    } catch (e) {
      setLog(`✗ ${(e as Error).message}`);
    } finally {
      setBusy("");
    }
  }

  async function evaluate() {
    setBusy("eval");
    setLog("running evaluate…");
    try {
      const r = await api.evaluate({ backend: jb, floor, top_n: 20 });
      setLog(`✓ evaluate → ${r.evaluated} evaluated · ${r.pursue} pursue · ${r.review} review · ${r.killed} killed`);
      onRan();
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
          <h1>Run pipeline</h1>
          <div className="sub">Trigger generation and screening. Router = Tencent (auto); cc = manual Claude Code handoff.</div>
        </div>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h3>A · GENERATE</h3>
          <div className="field">
            <label>Backend</label>
            <Seg opts={GEN_BACKENDS} val={gb} onChange={setGb} />
          </div>
          <div className="field">
            <label>Sources {srcs.length === 0 && <span className="faint">(all)</span>}</label>
            <div className="seg">
              {SOURCES.map((s) => (
                <button key={s.key} className={srcs.includes(s.key) ? "on" : ""} onClick={() => toggleSrc(s.key)}>
                  {s.label}
                </button>
              ))}
            </div>
          </div>
          <div className="field">
            <label>Top N in report</label>
            <input className="txt" type="number" value={topN} onChange={(e) => setTopN(+e.target.value)} />
          </div>
          <button className="btn" disabled={!!busy} onClick={gen}>
            {busy === "gen" ? <span className="spinner" /> : "Run generate"}
          </button>
        </div>

        <div className="card">
          <h3>B · EVALUATE</h3>
          <div className="field">
            <label>Judge backend</label>
            <Seg opts={JUDGE_BACKENDS} val={jb} onChange={setJb} />
          </div>
          <div className="field">
            <label>Kill-gate floor ({floor.toFixed(2)})</label>
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
            The LLM judge runs only on kill-gate survivors (token-thrifty). <b>cc</b> writes a request pack and pauses
            for a manual Claude Code session.
          </div>
          <button className="btn" disabled={!!busy} onClick={evaluate}>
            {busy === "eval" ? <span className="spinner" /> : "Run evaluate"}
          </button>
        </div>
      </div>

      <div className="card" style={{ marginTop: 18 }}>
        <h3>RESULT</h3>
        <div className="runlog">{log || "—"}</div>
      </div>
    </>
  );
}
