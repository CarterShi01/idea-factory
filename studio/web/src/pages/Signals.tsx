import { useEffect, useState } from "react";
import { api } from "../api";
import type { Signal } from "../types";
import { SyntheticChip } from "../components/VerdictChip";
import { sourceLabel } from "../labels";

export function Signals() {
  const [rows, setRows] = useState<Signal[] | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.signals().then(setRows).catch((e) => setErr((e as Error).message));
  }, []);

  if (err) return <div className="empty">{err}</div>;
  if (!rows) return <div className="empty"><span className="spinner" /> 加载中…</div>;

  return (
    <>
      <div className="topbar">
        <div>
          <h1>信号</h1>
          <div className="sub">三个来源共 {rows.length} 条归一化信号</div>
        </div>
      </div>
      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr>
              <th>痛点 / 信号</th>
              <th style={{ width: 130 }}>来源</th>
              <th style={{ width: 110 }}>观察时间</th>
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
                  {sourceLabel(s.source)}
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
