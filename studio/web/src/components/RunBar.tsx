import type { RunSummary } from "../types";
import { navigate } from "../hooks/useHashRoute";
import type { Route as R } from "../hooks/useHashRoute";

/** Top bar: brand + run selector + the two non-run destinations (controls/profile)
 *  + logout. The run selector is the spine of the whole console — everything
 *  else drills from the selected run. */
export function RunBar({
  runs,
  runId,
  route,
  onLogout,
}: {
  runs: RunSummary[];
  runId: string | null;
  route: R;
  onLogout: () => void;
}) {
  const go = (r: R) => navigate(r);
  const active = (name: string) => route.name === name;
  return (
    <header className="runbar">
      <div className="runbar-brand" onClick={() => runId && go({ name: "run", runId })} role="button">
        <span className="logo">爱</span>
        <span className="rb-name">创意工厂<small>调试台</small></span>
      </div>

      <label className="rb-run">
        <span className="rb-run-label">运行</span>
        <select
          value={runId ?? ""}
          onChange={(e) => go({ name: "run", runId: e.target.value })}
        >
          {runs.length === 0 && <option value="">（还没有运行 —— 去「运行」触发一次）</option>}
          {runs.map((r) => (
            <option key={r.run_id} value={r.run_id}>
              {r.run_id}{r.has_artifacts ? "" : " · 仅日志"} · {r.week}
            </option>
          ))}
        </select>
      </label>

      <nav className="rb-nav">
        <a className={active("run") || active("stage") || active("idea") ? "on" : ""}
           href={runId ? `#/run/${encodeURIComponent(runId)}` : "#/"}>漏斗</a>
        <a className={active("controls") ? "on" : ""} href="#/controls">运行</a>
        <a className={active("profile") ? "on" : ""} href="#/profile">画像</a>
      </nav>
      <button className="btn ghost rb-logout" onClick={onLogout}>登出</button>
    </header>
  );
}
