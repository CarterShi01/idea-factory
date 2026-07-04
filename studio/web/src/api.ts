import type { Decision, Idea, Overview, Signal, Version } from "./types";

const vq = (version?: string) => (version ? `?version=${encodeURIComponent(version)}` : "");

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const msg = await res.json().catch(() => ({}));
    throw new Error((msg as { error?: string }).error || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  me: () => req<{ auth: boolean; authed: boolean }>("/api/me"),
  login: (password: string) =>
    req<{ ok: boolean }>("/api/login", { method: "POST", body: JSON.stringify({ password }) }),
  logout: () => req<unknown>("/api/logout", { method: "POST" }),

  versions: () => req<Version[]>("/api/versions"),
  overview: (version?: string) => req<Overview>(`/api/overview${vq(version)}`),
  ideas: (version?: string) => req<Idea[]>(`/api/ideas${vq(version)}`),
  decisions: (version?: string) => req<Decision[]>(`/api/decisions${vq(version)}`),
  signals: () => req<Signal[]>("/api/signals"),

  generate: (body: Record<string, unknown>) =>
    req<{ raw_count: number; signal_count: number; deduped_count: number; candidate_count: number }>(
      "/api/run/generate",
      { method: "POST", body: JSON.stringify(body) },
    ),
  evaluate: (body: Record<string, unknown>) =>
    req<{ evaluated: number; pursue: number; review: number; killed: number }>("/api/run/evaluate", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  inbox: (body: Record<string, unknown>) =>
    req<{ ok: boolean }>("/api/inbox", { method: "POST", body: JSON.stringify(body) }),
};
