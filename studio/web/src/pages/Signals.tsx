import { useEffect, useState } from "react";
import { api } from "../api";
import type { Signal } from "../types";
import { SyntheticChip } from "../components/VerdictChip";

const SRC_LABEL: Record<string, string> = {
  external_event: "External event",
  brain_inbox: "Founder inbox",
  pain_persona: "Simulated pain",
};

export function Signals() {
  const [rows, setRows] = useState<Signal[] | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.signals().then(setRows).catch((e) => setErr((e as Error).message));
  }, []);

  if (err) return <div className="empty">{err}</div>;
  if (!rows) return <div className="empty"><span className="spinner" /> loading…</div>;

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Signals</h1>
          <div className="sub">{rows.length} normalized signals across the three sources</div>
        </div>
      </div>
      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr>
              <th>Pain / signal</th>
              <th style={{ width: 130 }}>Source</th>
              <th style={{ width: 110 }}>Observed</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.id}>
                <td>
                  <div style={{ fontWeight: 600 }}>
                    {s.title} {s.confidence === "synthetic" && <SyntheticChip />}
                  </div>
                  <div className="dim" style={{ fontSize: 12.5, marginTop: 3 }}>{s.pain_statement}</div>
                </td>
                <td className="dim">
                  {SRC_LABEL[s.source] ?? s.source}
                  <div className="faint mono" style={{ fontSize: 11.5 }}>{s.source_name}</div>
                </td>
                <td className="faint mono">{s.observed_on}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
