import { useEffect, useState } from "react";
import { api } from "../api";
import type { FounderProfile } from "../types";

// Fallback labels if config/founder.json ships no _labels block. The backend's
// PUT validation is the real guard on the required keys; this is display only.
const FALLBACK_LABELS: Record<string, string> = {
  identity: "身份定位",
  capital_rmb: "启动资金(人民币)",
  capital_note: "资金说明",
  skills: "技能",
  network: "可低成本触达的人脉 / 渠道",
  language_region_edge: "语言 / 地域独占优势(护城河)",
  reach_keywords_en: "可触达用户关键词(英文)",
  reach_keywords_zh: "可触达用户关键词(中文)",
  hard_constraints: "硬约束",
  anti_fit: "明显不适合他的方向",
};

// Long free-text fields → textarea; the rest of the strings are single-line.
const TEXT_FIELDS: { key: keyof FounderProfile; rows: number }[] = [
  { key: "identity", rows: 3 },
  { key: "capital_note", rows: 4 },
];
// List fields rendered as add/remove multi-row editors.
const LIST_FIELDS: (keyof FounderProfile)[] = [
  "skills",
  "network",
  "language_region_edge",
  "reach_keywords_en",
  "reach_keywords_zh",
  "hard_constraints",
  "anti_fit",
];

export function Profile() {
  const [prof, setProf] = useState<FounderProfile | null>(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .founderProfile()
      .then(setProf)
      .catch((e) => setErr((e as Error).message));
  }, []);

  if (err && !prof) return <div className="card err">加载画像失败：{err}</div>;
  if (!prof) {
    return (
      <div className="login-wrap">
        <span className="spinner" />
      </div>
    );
  }

  const p = prof; // non-null narrowing for closures below
  const labels = (p._labels || {}) as Record<string, string>;
  const labelOf = (k: string) => labels[k] || FALLBACK_LABELS[k] || k;

  const setField = (k: string, v: unknown) => {
    setProf({ ...p, [k]: v });
    setMsg("");
  };
  const asList = (k: keyof FounderProfile): string[] =>
    Array.isArray(p[k]) ? (p[k] as string[]) : [];
  const setItem = (k: keyof FounderProfile, i: number, v: string) => {
    const arr = [...asList(k)];
    arr[i] = v;
    setField(k as string, arr);
  };
  const addItem = (k: keyof FounderProfile) => setField(k as string, [...asList(k), ""]);
  const delItem = (k: keyof FounderProfile, i: number) =>
    setField(k as string, asList(k).filter((_, j) => j !== i));

  async function save() {
    setBusy(true);
    setErr("");
    setMsg("");
    // Trim + drop empty list rows before sending (empties are UI scratch space).
    const clean: FounderProfile = { ...p };
    for (const k of LIST_FIELDS) {
      if (Array.isArray(clean[k])) {
        clean[k] = (clean[k] as string[]).map((s) => s.trim()).filter(Boolean) as never;
      }
    }
    try {
      await api.saveFounderProfile(clean);
      setProf(clean);
      setMsg("✓ 已保存 · 下次运行流水线自动使用新画像");
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="topbar">
        <div>
          <h1>创始人画像</h1>
          <div className="sub">
            编辑『谁来执行』约束层(config/founder.json)。保存后下次运行流水线的打分因子与 LLM
            prompt 自动使用新画像。
          </div>
        </div>
        <button className="btn" disabled={busy} onClick={save}>
          {busy ? <span className="spinner" /> : "保存"}
        </button>
      </div>

      <div className="card" style={{ marginBottom: 18 }}>
        <div className="field">
          <label>{labelOf("identity")}</label>
          <textarea
            className="txt"
            rows={TEXT_FIELDS[0].rows}
            value={String(p.identity ?? "")}
            onChange={(e) => setField("identity", e.target.value)}
          />
        </div>
        <div className="grid cols-2">
          <div className="field">
            <label>{labelOf("capital_rmb")}</label>
            <input
              className="txt"
              type="number"
              value={Number(p.capital_rmb ?? 0)}
              onChange={(e) => setField("capital_rmb", Number(e.target.value))}
            />
          </div>
        </div>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>{labelOf("capital_note")}</label>
          <textarea
            className="txt"
            rows={TEXT_FIELDS[1].rows}
            value={String(p.capital_note ?? "")}
            onChange={(e) => setField("capital_note", e.target.value)}
          />
        </div>
      </div>

      {LIST_FIELDS.map((k) => (
        <div className="card" style={{ marginBottom: 14 }} key={String(k)}>
          <h3>{labelOf(String(k))}</h3>
          {asList(k).map((item, i) => (
            <div key={i} style={{ display: "flex", gap: 8, marginBottom: 8 }}>
              <input
                className="txt"
                value={item}
                onChange={(e) => setItem(k, i, e.target.value)}
              />
              <button
                className="btn ghost"
                onClick={() => delItem(k, i)}
                style={{ whiteSpace: "nowrap", padding: "0 12px" }}
                aria-label="删除该项"
                title="删除"
              >
                ✕
              </button>
            </div>
          ))}
          <button className="btn ghost" onClick={() => addItem(k)}>
            + 添加一项
          </button>
        </div>
      ))}

      <div className="card">
        <h3>结果</h3>
        <div className="runlog">{err ? `✗ ${err}` : msg || "编辑后点右上角『保存』。"}</div>
      </div>
    </>
  );
}
