import type { Compound } from "./types";

export const COMPOUND_COLOR: Record<string, string> = {
  SOFT: "var(--soft)",
  MEDIUM: "var(--medium)",
  HARD: "var(--hard)",
  INTERMEDIATE: "var(--inter)",
  WET: "var(--wet)",
  UNKNOWN: "var(--muted)",
};

export const COMPOUND_HEX: Record<string, string> = {
  SOFT: "#ff4d5e",
  MEDIUM: "#ffd23f",
  HARD: "#e9eef5",
  INTERMEDIATE: "#3ecf6e",
  WET: "#3f8cff",
  UNKNOWN: "#7d8aa0",
};

export function initial(c: Compound | string | null | undefined): string {
  if (!c) return "?";
  return c === "INTERMEDIATE" ? "I" : c[0];
}

export function lapTime(s: number | null | undefined): string {
  if (s == null) return "—";
  const m = Math.floor(s / 60);
  return `${m}:${(s - m * 60).toFixed(3).padStart(6, "0")}`;
}

export function signed(s: number | null | undefined, digits = 1): string {
  if (s == null) return "—";
  const v = Math.abs(s) < 0.05 ? 0 : s;
  return `${v > 0 ? "+" : v < 0 ? "−" : "±"}${Math.abs(v).toFixed(digits)}`;
}
