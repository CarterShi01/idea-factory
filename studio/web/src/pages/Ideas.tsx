import { Fragment, useEffect, useState } from "react";
import { api } from "../api";
import type { Idea } from "../types";
import { FactorBars } from "../components/FactorBar";
import { SyntheticChip } from "../components/VerdictChip";

export function Ideas() {
  const [ideas, setIdeas] = useState<Idea[] | null>(null);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    api.ideas().then(setIdeas).catch((e) => setErr((e as Error).message));
  }, []);

  if (err) return <div className="empty">{err}</div>;
  if (!ideas) return <div className="empty"><span className="spinner" /> loading…</div>;
  if (!ideas.length) return <div className="empty">No candidates yet — run the generate stage.</div>;

  return (
    <>
      <div className="topbar">
        <div>
          <h1>Ideas</h1>
          <div className="sub">{ideas.length} ranked candidates · alpha = factor-weighted, time-decayed</div>
        </div>
      </div>
      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr>
              <th style={{ width: 34 }}>#</th>
              <th>Idea</th>
              <th style={{ width: 90 }}>Source</th>
              <th style={{ width: 70 }}>Alpha</th>
              <th style={{ width: 70 }}>Decay</th>
            </tr>
          </thead>
          <tbody>
            {ideas.map((it, i) => (
              <Fragment key={it.id}>
                <tr style={{ cursor: "pointer" }} onClick={() => setOpen(open === it.id ? null : it.id)}>
                  <td className="faint mono">{i + 1}</td>
                  <td>
                    <div style={{ fontWeight: 600 }}>
                      {it.title} {it.confidence === "synthetic" && <SyntheticChip />}
                    </div>
                    <div className="dim" style={{ fontSize: 12.5, marginTop: 3 }}>{it.pain}</div>
                  </td>
                  <td className="dim mono">{it.source.replace("_event", "").replace("_inbox", "")}</td>
                  <td className="alpha">{it.alpha.toFixed(3)}</td>
                  <td className="faint mono">{it.decay.toFixed(2)}</td>
                </tr>
                {open === it.id && (
                  <tr>
                    <td />
                    <td colSpan={4} style={{ paddingTop: 0 }}>
                      <div className="grid cols-2" style={{ gap: 18, paddingBottom: 6 }}>
                        <div>
                          <div className="kv"><b>Solution:</b> {it.solution}</div>
                          <div className="kv"><b>Target user:</b> {it.target_user}</div>
                          <div className="kv faint">{it.source} · {it.observed_on}{it.category ? ` · ${it.category}` : ""}</div>
                        </div>
                        <div><FactorBars factors={it.factors} /></div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
