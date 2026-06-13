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
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <div className="login">
        <div className="brand" style={{ justifyContent: "center", paddingBottom: 22 }}>
          <div className="logo">IF</div>
          <div className="name">
            Idea Factory<small>STUDIO</small>
          </div>
        </div>
        <div className="card">
          <h2>Sign in</h2>
          <p>Control panel for the 3-source idea engine.</p>
          <form onSubmit={submit}>
            <input
              className="txt"
              type="password"
              placeholder="Password"
              value={pw}
              autoFocus
              onChange={(e) => setPw(e.target.value)}
            />
            <button className="btn" style={{ width: "100%", marginTop: 14 }} disabled={busy}>
              {busy ? <span className="spinner" /> : "Enter"}
            </button>
          </form>
          {err && <div className="err">{err}</div>}
        </div>
      </div>
    </div>
  );
}
