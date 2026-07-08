import { useState } from "react";
import type { TraceRow } from "../types";
import { CostBadge } from "./CostBadge";

/** Raw LLM call inspector: system + user prompt, response text/data, and the
 *  usage/cost/latency badge. This is the "看每一步 LLM 到底跑了什么" surface. */
export function TracePane({ label, rows }: { label: string; rows: TraceRow[] }) {
  return (
    <div className="trace-pane">
      <div className="trace-label">{label}（{rows.length} 次 LLM 调用）</div>
      {rows.map((t, i) => (
        <TraceRowView key={i} t={t} />
      ))}
    </div>
  );
}

function TraceRowView({ t }: { t: TraceRow }) {
  const [open, setOpen] = useState(false);
  const verdict = (t.response?.data as { verdict?: string } | undefined)?.verdict;
  return (
    <div className="trace-row">
      <button className="trace-toggle" onClick={() => setOpen((v) => !v)}>
        <span className="mono faint">{open ? "▾" : "▸"}</span>
        <span className="mono">{t.model || "—"}</span>
        {t.prompt_version && <span className="faint mono">{t.prompt_version}</span>}
        {verdict && <span className="mono">→ {verdict}</span>}
        <CostBadge usage={t.usage} cost={t.cost} latencyMs={t.latency_ms} />
      </button>
      {open && (
        <div className="trace-body">
          {t.request?.system && (
            <div className="trace-block">
              <div className="trace-btitle">SYSTEM</div>
              <pre>{t.request.system}</pre>
            </div>
          )}
          {t.request?.user && (
            <div className="trace-block">
              <div className="trace-btitle">USER（含创始人画像 + 该 idea 上下文）</div>
              <pre>{t.request.user}</pre>
            </div>
          )}
          <div className="trace-block">
            <div className="trace-btitle">RESPONSE</div>
            <pre>{t.response?.text || JSON.stringify(t.response?.data ?? t.response, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
