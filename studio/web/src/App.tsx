import { useEffect, useState } from "react";
import { api } from "./api";
import { Login } from "./pages/Login";
import { RunPanel } from "./pages/RunPanel";
import { Profile } from "./pages/Profile";
import { RunFunnel } from "./pages/RunFunnel";
import { StageDrill } from "./pages/StageDrill";
import { IdeaLineage } from "./pages/IdeaLineage";
import { RunBar } from "./components/RunBar";
import { useHashRoute, navigate } from "./hooks/useHashRoute";
import type { RunSummary } from "./types";

type Auth = "checking" | "in" | "out";

export function App() {
  const [auth, setAuth] = useState<Auth>("checking");
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const route = useHashRoute();

  useEffect(() => {
    api.me().then((m) => setAuth(!m.auth || m.authed ? "in" : "out")).catch(() => setAuth("out"));
  }, []);

  function loadRuns(jumpLatest = false) {
    api.runs().then((rs) => {
      setRuns(rs);
      if ((jumpLatest || route.name === "home") && rs[0]) navigate({ name: "run", runId: rs[0].run_id });
    }).catch(() => setRuns([]));
  }

  useEffect(() => {
    if (auth === "in") loadRuns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth]);

  if (auth === "checking") return <div className="login-wrap"><span className="spinner" /></div>;
  if (auth === "out") return <Login onDone={() => setAuth("in")} />;

  async function logout() {
    await api.logout().catch(() => {});
    setAuth("out");
  }

  // the run currently in focus (from the URL, else the newest)
  const activeRun =
    route.name === "run" || route.name === "stage" || route.name === "idea"
      ? route.runId
      : runs[0]?.run_id ?? null;

  return (
    <div className="studio">
      <RunBar runs={runs} runId={activeRun} route={route} onLogout={logout} />
      <main className="stage-main">
        {route.name === "controls" && <RunPanel onRan={() => loadRuns(true)} />}
        {route.name === "profile" && <Profile />}
        {route.name === "run" && <RunFunnel key={route.runId} runId={route.runId} />}
        {route.name === "stage" && <StageDrill key={route.runId + route.stage} runId={route.runId} stage={route.stage} />}
        {route.name === "idea" && <IdeaLineage key={route.runId + route.ideaId} runId={route.runId} ideaId={route.ideaId} />}
        {route.name === "home" && (
          <div className="empty">
            {runs.length ? "选择一个运行…" : "还没有任何运行 —— 打开「运行」触发一次 idea run。"}
          </div>
        )}
      </main>
    </div>
  );
}
