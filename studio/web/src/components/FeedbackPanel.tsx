import { useEffect, useState } from "react";
import { api } from "../api";
import type { FeedbackRow } from "../types";
import { FEEDBACK_LABELS, feedbackLabelZh } from "../labels";

/** 反馈闭环采集(问题定位型标签 + other 自由文本)。每次提交在后端冻结这条 idea 的
 *  完整血统快照,自包含地存进 feedback.jsonl —— 作为日后在 CC 里人工盘 case、
 *  聚合、决定怎么改代码的数据底座。不触发任何自动优化(刻意为之)。 */
export function FeedbackPanel({ runId, ideaId }: { runId: string; ideaId: string }) {
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [note, setNote] = useState("");
  const [history, setHistory] = useState<FeedbackRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState("");

  async function loadHistory() {
    try {
      setHistory(await api.feedbackFor(runId, ideaId));
    } catch {
      /* 历史加载失败不致命,静默 */
    }
  }
  useEffect(() => {
    void loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, ideaId]);

  function toggle(id: string) {
    setPicked((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
    setSaved(false);
  }

  async function submit() {
    const labels = [...picked];
    if ((labels.length === 0 && !note.trim()) || busy) return;
    setBusy(true);
    setErr("");
    try {
      await api.feedback(runId, ideaId, labels, note.trim());
      setPicked(new Set());
      setNote("");
      setSaved(true);
      await loadHistory();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const canSubmit = (picked.size > 0 || note.trim().length > 0) && !busy;

  return (
    <div className="feedback">
      <div className="ask-head">
        <b>反馈 · 记一条 case</b>
        <span className="faint tiny">存快照到 feedback.jsonl,供你日后在 CC 里盘</span>
      </div>
      <div className="fb-chips">
        {FEEDBACK_LABELS.map((l) => (
          <button
            key={l.id}
            className={`reason-chip clickable${picked.has(l.id) ? " on" : ""}`}
            title={l.hint}
            onClick={() => toggle(l.id)}
            disabled={busy}
          >
            {l.zh}
          </button>
        ))}
      </div>
      <textarea
        className="txt fb-note"
        placeholder="other —— 补充一段话:哪里判得不对、你会怎么改、这条为什么值得记…（可只填这里，不选标签）"
        value={note}
        onChange={(e) => {
          setNote(e.target.value);
          setSaved(false);
        }}
        disabled={busy}
        rows={3}
      />
      <div className="fb-actions">
        <button className="btn" onClick={submit} disabled={!canSubmit}>
          {busy ? <span className="spinner" /> : "记下这条反馈"}
        </button>
        {saved && <span className="faint tiny">已记录 ✓</span>}
        {err && <span className="err">{err}</span>}
      </div>
      {history.length > 0 && (
        <div className="fb-history">
          <div className="faint tiny">这条 idea 的历史反馈（{history.length}）</div>
          {history.map((h) => (
            <div className="fb-row" key={h.feedback_id}>
              <span className="faint mono tiny">{h.ts.slice(0, 16).replace("T", " ")}</span>
              {h.labels.map((id) => (
                <span key={id} className="reason-chip">{feedbackLabelZh(id)}</span>
              ))}
              {h.note && <span className="fb-note-text">{h.note}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
