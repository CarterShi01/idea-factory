import { useState } from "react";
import { api } from "../api";

export function Login({ onDone }: { onDone: () => void }) {
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await api.login(pw);
      onDone();
    } catch {
      setErr("密码错误");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <div className="login">
        <div className="brand" style={{ justifyContent: "center", paddingBottom: 22 }}>
          <div className="logo">创</div>
          <div className="name">
            创意工厂<small>控制台</small>
          </div>
        </div>
        <div className="card">
          <h2>登录</h2>
          <p>三源创意引擎的控制面板。</p>
          <form onSubmit={submit}>
            <input
              className="txt"
              type="password"
              placeholder="请输入密码"
              value={pw}
              autoFocus
              onChange={(e) => setPw(e.target.value)}
            />
            <button className="btn" style={{ width: "100%", marginTop: 14 }} disabled={busy}>
              {busy ? <span className="spinner" /> : "进入"}
            </button>
          </form>
          {err && <div className="err">{err}</div>}
        </div>
      </div>
    </div>
  );
}
