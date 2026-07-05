import { useEffect, useState } from "react";
import { api } from "../api";
import type { FunnelReport } from "../types";

const STAGE_LABEL: Record<string, string> = {
  triage_signal: "①② 信号硬红线(>24月过期)",
  triage_candidate: "②候选硬红线(anti-fit)",
  diligence: "⑥裁决(证据门+强制分布)",
};

function stageLabel(stage: string): string {
  return STAGE_LABEL[stage] ?? stage;
}

export function Funnel() {
  const [report, setReport] = useState<FunnelReport | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.funnel().then(setReport).catch((e) => setErr((e as Error).message));
  }, []);

  if (err) return <div className="empty">{err}</div>;
  if (!report) return <div className="empty"><span className="spinner" /> 加载中…</div>;

  const stages = Object.entries(report.stage_survival);
  const hasData = stages.length > 0;

  return (
    <>
      <div className="topbar">
        <div>
          <h1>漏斗</h1>
          <div className="sub">
            只读,读自 data/ledger/*.jsonl —— 用 idea-gen --use-triage / idea-eval --require-evidence 跑一次才有数据。
          </div>
        </div>
      </div>

      {!hasData && (
        <div className="card">
          <div className="muted-note">
            暂无 ledger 数据。这两个开关默认关闭(不改变现有默认产出),需要显式启用:
            <br />
            <code>idea-gen --use-triage</code> 、 <code>idea-eval --require-evidence</code>
          </div>
        </div>
      )}

      {hasData && (
        <div className="card" style={{ marginBottom: 18 }}>
          <h3>各段存活率</h3>
          {stages.map(([stage, s]) => (
            <div className="fbar" key={stage}>
              <span className="fname">{stageLabel(stage)}</span>
              <span className="track">
                <span className="fill" style={{ width: `${Math.round(s.rate * 100)}%` }} />
              </span>
              <span className="fval">
                {s.survived} 存活 / {s.killed} 杀（{Math.round(s.rate * 100)}%）
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="grid cols-2">
        <div className="card">
          <h3>杀因分布</h3>
          {Object.keys(report.kill_reasons).length === 0 && <div className="faint">（无）</div>}
          {Object.entries(report.kill_reasons)
            .sort((a, b) => b[1] - a[1])
            .map(([reason, n]) => (
              <div className="kv" key={reason}>
                <b>{reason}：</b> {n}
              </div>
            ))}
        </div>
        <div className="card">
          <h3>裁决分布</h3>
          {Object.keys(report.verdict_distribution).length === 0 && <div className="faint">（无）</div>}
          {Object.entries(report.verdict_distribution)
            .sort((a, b) => b[1] - a[1])
            .map(([verdict, n]) => (
              <div className="kv" key={verdict}>
                <span className={`chip ${verdict}`}>{verdict}</span> {n}
              </div>
            ))}
        </div>
      </div>

      <div className="card" style={{ marginTop: 18 }}>
        <h3>预测 vs 实际（retro）</h3>
        <div className="kv"><b>已记录结果：</b> {report.outcomes.count}</div>
        {report.outcomes.avg_prediction_error !== null && (
          <div className="kv">
            <b>平均预测误差：</b> {(report.outcomes.avg_prediction_error * 100).toFixed(1)}%
          </div>
        )}
        <div className="kv"><b>已产生首笔收入事件：</b> {report.outcomes.first_revenue_events}</div>
        {report.outcomes.lessons.map((l, i) => (
          <div className="kv faint" key={i}>· {l}</div>
        ))}
      </div>
    </>
  );
}
