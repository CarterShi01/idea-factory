import { useEffect, useState } from "react";
import { api } from "./api";
import { Sidebar, type Tab } from "./components/Sidebar";
import { Login } from "./pages/Login";
import { Overview } from "./pages/Overview";
import { Ideas } from "./pages/Ideas";
import { Decisions } from "./pages/Decisions";
import { Signals } from "./pages/Signals";
import { RunPanel } from "./pages/RunPanel";
import type { Version } from "./types";
import { Profile } from "./pages/Profile";
import { Funnel } from "./pages/Funnel";

type Auth = "checking" | "in" | "out";

export function App() {
  const [auth, setAuth] = useState<Auth>("checking");
  const [tab, setTab] = useState<Tab>("overview");
  const [nonce, setNonce] = useState(0); // bump to force-refresh pages after a run
  const [versions, setVersions] = useState<Version[]>([]);
  const [version, setVersion] = useState<string | undefined>(undefined); // undefined = latest

  useEffect(() => {
    api
      .me()
      .then((m) => setAuth(!m.auth || m.authed ? "in" : "out"))
      .catch(() => setAuth("out"));
  }, []);

  // Load the version list once authed; default the selection to the latest.
  function loadVersions(selectLatest = false) {
    api
      .versions()
      .then((vs) => {
        setVersions(vs);
        if (selectLatest || version === undefined) setVersion(vs[0]?.id);
      })
      .catch(() => setVersions([]));
  }

  useEffect(() => {
    if (auth === "in") loadVersions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth]);

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

  // After a run: a fresh version was committed — reload the list and jump to it.
  const refresh = () => {
    setNonce((n) => n + 1);
    loadVersions(true);
  };

  return (
    <div className="app">
      <Sidebar
        tab={tab}
        onTab={setTab}
        onLogout={logout}
        versions={versions}
        version={version}
        onVersion={setVersion}
      />
      <main className="main" key={tab + nonce + (version ?? "latest")}>
        {tab === "overview" && <Overview version={version} />}
        {tab === "ideas" && <Ideas version={version} />}
        {tab === "decisions" && <Decisions version={version} />}
        {tab === "funnel" && <Funnel />}
        {tab === "signals" && <Signals />}
        {tab === "run" && <RunPanel onRan={refresh} />}
        {tab === "profile" && <Profile />}
      </main>
    </div>
  );
}
