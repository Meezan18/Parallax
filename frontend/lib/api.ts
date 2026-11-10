import type { EventInfo, RaceSummary, SessionInfo, StopInfo } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const WS_URL = API_URL.replace(/^http/, "ws");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new Error(`Can't reach the strategy server at ${API_URL}. Start the backend and try again.`);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  schedule: (year: number) => request<EventInfo[]>(`/api/schedule/${year}`),
  loadRace: (body: { year?: number; round?: number; demo?: boolean }) =>
    request<RaceSummary>("/api/races/load", { method: "POST", body: JSON.stringify(body) }),
  createSession: (body: {
    race_id: number;
    driver: string;
    mode: "auto" | "fixed";
    stops: StopInfo[];
    branch_lap: number;
    seconds_per_lap: number;
  }) => request<SessionInfo>("/api/sessions", { method: "POST", body: JSON.stringify(body) }),
};
