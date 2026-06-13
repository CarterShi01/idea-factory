import { useEffect, useState } from "react";
import { api } from "../api";
import type { Overview as OverviewT } from "../types";
import { StatCard } from "../components/StatCard";

const STAGES = [
  { t: "collect", d: "3 sources", llm: false },
  { t: "normalize", d: "pain", llm: false },
  { t: "dedup", d: "seen?", llm: false },
  { t: "generate", d: "A · LLM", llm: true },
  { t: "score", d: "factors", llm: false },
  { t: "rank", d: "alpha", llm: false },
  { t: "kill-gate", d: "rules", llm: false },
  { t: "judge", d: "B · LLM", llm: true },
  { t: "memos", d: "decide", llm: false },
];

export function Overview() {
  const [o, setO] = useState<OverviewT | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.overview().then(setO).catch((e) => setErr((e as Error).message));
  }, []);

  if (err) return <div className="empty">{err}</div>;
  if (!o) return <div className="empty"><span className="spinner" /> loading…</div>;

  const fmt = (s: string | null) => (s ? new Date(s).toLocaleString() : "—");

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Overview</h1>
          <div className="sub">Daily pipeline: external events · founder inbox · simulated pain → vetted ideas</div>
        </div>
      </div>

      <div className="grid cols-4" style={{ marginBottom: 18 }}>
        <StatCard label="Candidates" value={o.candidates} hint={`generated ${fmt(o.last_generate)}`} />
        <StatCard label="Pursue" value={o.verdicts.pursue} color="var(--pursue)" hint="worth building now" />
        <StatCard label="Review" value={o.verdicts.review} color="var(--review)" hint="validate cheaply" />
        <StatCard label="Killed" value={o.verdicts.kill} color="var(--kill)" hint="screened out" />
      </div>

      <div className="card" style={{ marginBottom: 18 }}>
        <h3>PIPELINE</h3>
        <div className="flow">
          {STAGES.map((s, i) => (
            <span key={s.t} style={{ display: "flex", alignItems: "stretch" }}>
              <span className={`node ${s.llm ? "llm" : ""}`}>
                <div className="t">{s.t}</div>
                <div className="d">{s.d}</div>
              </span>
              {i < STAGES.length - 1 && <span className="arrow">→</span>}
            </span>
          ))}
        </div>
        <div className="muted-note" style={{ marginTop: 12 }}>
          Blue stages call an LLM (Tencent router / manual CC). Everything else is offline, zero-token.
          {o.judged_by_llm ? " · last screen used the LLM judge." : " · last screen was rule-only."}
        </div>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h3>FACTOR LIBRARY</h3>
          <div className="muted-note" style={{ marginBottom: 8 }}>
            Pure functions shared by generation &amp; evaluation (single source of truth).
          </div>
          {o.factor_names.map((f) => (
            <span key={f} className="chip" style={{ marginRight: 6, marginBottom: 6, color: "var(--accent)", background: "var(--accent-soft)" }}>
              {f}
            </span>
          ))}
        </div>
        <div className="card">
          <h3>LAST RUN</h3>
          <div className="kv"><b>Generated:</b> {fmt(o.last_generate)}</div>
          <div className="kv"><b>Evaluated:</b> {fmt(o.last_evaluate)}</div>
          <div className="kv"><b>Evaluated count:</b> {o.evaluated}</div>
        </div>
      </div>
    </>
  );
}
