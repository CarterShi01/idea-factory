import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Decision, Verdict } from "../types";
import { VerdictChip } from "../components/VerdictChip";

const FILTERS: (Verdict | "all")[] = ["all", "pursue", "review", "kill"];

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
  if (!rows) return <div className="empty"><span className="spinner" /> loading…</div>;
  if (!rows.length) return <div className="empty">No decisions yet — run the evaluate stage.</div>;

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Decisions</h1>
          <div className="sub">Kill-gate + rubric screen. Each survivor gets a killer objection and a cheap test.</div>
        </div>
        <div className="seg">
          {FILTERS.map((f) => (
            <button key={f} className={filter === f ? "on" : ""} onClick={() => setFilter(f)}>
              {f}
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
            <div className="kv"><b>Riskiest assumption:</b> {d.riskiest_assumption}</div>
            <div className="kv"><span className="rat">▷ RAT:</span> {d.cheap_experiment}</div>
            <div className="faint" style={{ fontSize: 12, marginTop: 8 }}>
              judged by {d.judged_by}
              {d.killed_by.length ? ` · fatal: ${d.killed_by.join(", ")}` : ""}
              {d.risk_flags.length ? ` · ${d.risk_flags.length} risk flag(s)` : ""}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
