import { useEffect, useState } from "react";
import { api } from "./api";
import { Sidebar, type Tab } from "./components/Sidebar";
import { Login } from "./pages/Login";
import { Overview } from "./pages/Overview";
import { Ideas } from "./pages/Ideas";
import { Decisions } from "./pages/Decisions";
import { Signals } from "./pages/Signals";
import { RunPanel } from "./pages/RunPanel";
import { Profile } from "./pages/Profile";

type Auth = "checking" | "in" | "out";

export function App() {
  const [auth, setAuth] = useState<Auth>("checking");
  const [tab, setTab] = useState<Tab>("overview");
  const [nonce, setNonce] = useState(0); // bump to force-refresh pages after a run

  useEffect(() => {
    api
      .me()
      .then((m) => setAuth(!m.auth || m.authed ? "in" : "out"))
      .catch(() => setAuth("out"));
  }, []);

  if (auth === "checking") {
    return <div className="login-wrap"><span className="spinner" /></div>;
  }
  if (auth === "out") {
    return <Login onDone={() => setAuth("in")} />;
  }

  async function logout() {
    await api.logout().catch(() => {});
    setAuth("out");
  }

  const refresh = () => setNonce((n) => n + 1);

  return (
    <div className="app">
      <Sidebar tab={tab} onTab={setTab} onLogout={logout} />
      <main className="main" key={tab + nonce}>
        {tab === "overview" && <Overview />}
        {tab === "ideas" && <Ideas />}
        {tab === "decisions" && <Decisions />}
        {tab === "signals" && <Signals />}
        {tab === "run" && <RunPanel onRan={refresh} />}
        {tab === "profile" && <Profile />}
      </main>
    </div>
  );
}
