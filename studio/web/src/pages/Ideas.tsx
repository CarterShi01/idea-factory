import { Fragment, useEffect, useState } from "react";
import { api } from "../api";
import type { Idea } from "../types";
import { FactorBars } from "../components/FactorBar";
import { SyntheticChip } from "../components/VerdictChip";
import { sourceLabel } from "../labels";

export function Ideas({ version }: { version?: string }) {
  const [ideas, setIdeas] = useState<Idea[] | null>(null);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    api.ideas(version).then(setIdeas).catch((e) => setErr((e as Error).message));
  }, [version]);

  if (err) return <div className="empty">{err}</div>;
  if (!ideas) return <div className="empty"><span className="spinner" /> 加载中…</div>;
  if (!ideas.length) return <div className="empty">还没有候选创意 —— 先运行“生成”阶段。</div>;

  return (
    <>
      <div className="topbar">
        <div>
          <h1>创意</h1>
          <div className="sub">{ideas.length} 条已排序候选 · alpha = 因子加权 × 时间衰减</div>
        </div>
      </div>
      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr>
              <th style={{ width: 34 }}>#</th>
              <th>创意</th>
              <th style={{ width: 90 }}>来源</th>
              <th style={{ width: 70 }}>Alpha</th>
              <th style={{ width: 70 }}>衰减</th>
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
                  <td className="dim">{sourceLabel(it.source)}</td>
                  <td className="alpha">{it.alpha.toFixed(3)}</td>
                  <td className="faint mono">{it.decay.toFixed(2)}</td>
                </tr>
                {open === it.id && (
                  <tr>
                    <td />
                    <td colSpan={4} style={{ paddingTop: 0 }}>
                      <div className="grid cols-2" style={{ gap: 18, paddingBottom: 6 }}>
                        <div>
                          <div className="kv"><b>方案：</b> {it.solution}</div>
                          <div className="kv"><b>目标用户：</b> {it.target_user}</div>
                          <div className="kv faint">{sourceLabel(it.source)} · {it.observed_on}{it.category ? ` · ${it.category}` : ""}</div>
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
