import { useEffect, useState } from "react";

/** Minimal zero-dep hash router. A debug console needs bookmarkable/shareable
 *  deep links (run → stage → idea), so navigation lives in the URL hash. */

export type Route =
  | { name: "home" }
  | { name: "run"; runId: string }
  | { name: "stage"; runId: string; stage: string }
  | { name: "idea"; runId: string; ideaId: string }
  | { name: "controls" }
  | { name: "profile" };

export function parseHash(hash: string): Route {
  const h = hash.replace(/^#\/?/, "");
  const parts = h.split("/").filter(Boolean).map(decodeURIComponent);
  if (parts[0] === "controls") return { name: "controls" };
  if (parts[0] === "profile") return { name: "profile" };
  if (parts[0] === "run" && parts[1]) {
    if (parts[2] === "stage" && parts[3]) return { name: "stage", runId: parts[1], stage: parts[3] };
    if (parts[2] === "idea" && parts[3]) return { name: "idea", runId: parts[1], ideaId: parts[3] };
    return { name: "run", runId: parts[1] };
  }
  return { name: "home" };
}

export function href(r: Route): string {
  const e = encodeURIComponent;
  switch (r.name) {
    case "run": return `#/run/${e(r.runId)}`;
    case "stage": return `#/run/${e(r.runId)}/stage/${e(r.stage)}`;
    case "idea": return `#/run/${e(r.runId)}/idea/${e(r.ideaId)}`;
    case "controls": return "#/controls";
    case "profile": return "#/profile";
    default: return "#/";
  }
}

export function navigate(r: Route) {
  window.location.hash = href(r);
}

export function useHashRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));
  useEffect(() => {
    const on = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}
