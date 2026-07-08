import { useState } from "react";
import { api } from "../api";
import type { AskBackend, AskResult } from "../types";
import { CostBadge } from "./CostBadge";

/** 实时追问：就这条 idea 自由提问，router 即时答（未配则降级 mock），每轮落 trace。 */
export function AskPanel({ runId, ideaId }: { runId: string; ideaId: string }) {
  const [q, setQ] = useState("");
  const [backend, setBackend] = useState<AskBackend>("router");
  const [turns, setTurns] = useState<AskResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const PRESETS = ["为什么这条是这个裁决？", "为什么证据门没过？", "最该先验证哪个假设？"];

  async function ask(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    setBusy(true);
    setErr("");
    try {
      const r = await api.ask(runId, ideaId, text, backend);
      setTurns((t) => [...t, r]);
      setQ("");
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ask">
      <div className="ask-head">
        <b>实时追问</b>
        <div className="seg tiny">
          {(["router", "mock"] as AskBackend[]).map((b) => (
            <button key={b} className={backend === b ? "on" : ""} onClick={() => setBackend(b)}>
              {b === "router" ? "腾讯" : "模拟"}
            </button>
          ))}
        </div>
      </div>
      <div className="ask-presets">
        {PRESETS.map((p) => (
          <button key={p} className="reason-chip clickable" onClick={() => ask(p)} disabled={busy}>{p}</button>
        ))}
      </div>
      {turns.map((t, i) => (
        <div className="ask-turn" key={i}>
          <div className="ask-q">你：{t.question}</div>
          <div className="ask-a">
            <span className="ask-a-body">{t.answer}</span>
            <div className="ask-meta">
              <span className="faint">{t.backend === "mock" ? "模拟后端" : "腾讯 router"}</span>
              <CostBadge usage={t.usage} latencyMs={t.latency_ms} />
            </div>
          </div>
        </div>
      ))}
      <div className="ask-input">
        <input
          className="txt"
          placeholder="就这条 idea 追问任何一步为什么…（Enter 发送）"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask(q)}
          disabled={busy}
        />
        <button className="btn" onClick={() => ask(q)} disabled={busy || !q.trim()}>
          {busy ? <span className="spinner" /> : "问"}
        </button>
      </div>
      {err && <div className="err">{err}</div>}
    </div>
  );
}
