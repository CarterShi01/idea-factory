import { useEffect, useState } from "react";
import { api } from "../api";
import type { Overview as OverviewT } from "../types";
import { StatCard } from "../components/StatCard";
import { factorLabel } from "../labels";

const STAGES = [
  { t: "采集", d: "三源", llm: false },
  { t: "归一化", d: "提痛点", llm: false },
  { t: "去重", d: "已见过?", llm: false },
  { t: "生成", d: "A · LLM", llm: true },
  { t: "打分", d: "因子", llm: false },
  { t: "排序", d: "alpha", llm: false },
  { t: "淘汰闸", d: "规则", llm: false },
  { t: "评审", d: "B · LLM", llm: true },
  { t: "决策备忘", d: "定夺", llm: false },
];

export function Overview() {
  const [o, setO] = useState<OverviewT | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.overview().then(setO).catch((e) => setErr((e as Error).message));
  }, []);

  if (err) return <div className="empty">{err}</div>;
  if (!o) return <div className="empty"><span className="spinner" /> 加载中…</div>;

  const fmt = (s: string | null) => (s ? new Date(s).toLocaleString("zh-CN") : "—");

  return (
    <>
      <div className="topbar">
        <div>
          <h1>概览</h1>
          <div className="sub">每日管线：外部事件 · 灵感收件箱 · 模拟痛点 → 经初筛的靠谱创意</div>
        </div>
      </div>

      <div className="grid cols-4" style={{ marginBottom: 18 }}>
        <StatCard label="候选数" value={o.candidates} hint={`生成于 ${fmt(o.last_generate)}`} />
        <StatCard label="推进" value={o.verdicts.pursue} color="var(--pursue)" hint="值得现在就做" />
        <StatCard label="待验证" value={o.verdicts.review} color="var(--review)" hint="先廉价验证" />
        <StatCard label="淘汰" value={o.verdicts.kill} color="var(--kill)" hint="已被筛掉" />
      </div>

      <div className="card" style={{ marginBottom: 18 }}>
        <h3>管线</h3>
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
          蓝色阶段调用 LLM（腾讯 router / 手动 CC），其余全部离线、零 token。
          {o.judged_by_llm ? " · 上次评审用了 LLM 评委。" : " · 上次评审为纯规则。"}
        </div>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h3>因子库</h3>
          <div className="muted-note" style={{ marginBottom: 8 }}>
            生成与评估共用的纯函数（唯一真理来源）。
          </div>
          {o.factor_names.map((f) => (
            <span key={f} className="chip" style={{ marginRight: 6, marginBottom: 6, color: "var(--accent)", background: "var(--accent-soft)" }}>
              {factorLabel(f)}
            </span>
          ))}
        </div>
        <div className="card">
          <h3>最近运行</h3>
          <div className="kv"><b>已生成：</b> {fmt(o.last_generate)}</div>
          <div className="kv"><b>已评估：</b> {fmt(o.last_evaluate)}</div>
          <div className="kv"><b>评估数量：</b> {o.evaluated}</div>
        </div>
      </div>
    </>
  );
}
