"use client";

import type { Frame } from "@/lib/types";
import { useTween } from "@/lib/motion";
import { Tyre } from "./TimingTower";

/** Real car on the left, AI car on the right, the gap between them in the middle. */
export function DuelBar({ frames, teamColor }: { frames: Frame[]; teamColor: string }) {
  const f = frames[frames.length - 1];
  const sh = f.focus.shadow;
  const real = f.focus.real;
  const retired = sh.retired || (sh.delta == null && sh.active);
  const gain = sh.active && sh.delta != null ? -sh.delta : sh.active ? null : 0;
  const shown = useTween(gain, 650);
  const lastDelta = [...frames].reverse().find((x) => x.focus.shadow.delta != null)?.focus.shadow.delta ?? null;
  const state = retired ? "even" : gain == null || Math.abs(gain) < 0.05 ? "even" : gain > 0 ? "ahead" : "behind";

  const caption = retired
    ? `Real ${f.focus.driver} retired. AI was ${Math.abs(lastDelta ?? 0).toFixed(1)}s ${(lastDelta ?? 0) <= 0 ? "ahead" : "behind"}.`
    : !sh.active
      ? "Mirroring the real car until the AI takes over"
      : state === "ahead" ? "AI strategy is gaining" : state === "behind" ? "AI strategy is losing time" : "Dead level";

  return (
    <section className="panel duel" aria-label="Real car against AI car">
      <div className="duel-side">
        <div className="duel-who"><span className="duel-chip" style={{ background: teamColor }} />Real {f.focus.driver}</div>
        <div className="duel-pos num">P{real.position ?? "–"}</div>
        <div className="duel-meta">
          {real.compound && <Tyre compound={real.compound} size={18} />}
          <span className="num">{real.age ?? "–"} laps</span>
          <span>{real.stops.length} {real.stops.length === 1 ? "stop" : "stops"}</span>
        </div>
      </div>

      <div className={`duel-delta duel-delta--${state}`} aria-live="polite">
        <div className="duel-number num">
          {retired ? "DNF" : shown == null ? "–" : `${shown > 0.049 ? "+" : shown < -0.049 ? "−" : "±"}${Math.abs(shown).toFixed(1)}`}
          {!retired && shown != null && <span className="duel-unit">s</span>}
        </div>
        <div className="duel-caption">{caption}</div>
      </div>

      <div className="duel-side duel-side--ai">
        <div className="duel-who">AI {f.focus.driver}<span className="duel-chip duel-chip--ai" /></div>
        <div className="duel-pos num">P{sh.position ?? "–"}</div>
        <div className="duel-meta">
          <Tyre compound={sh.compound} size={18} />
          <span className="num">{sh.age} laps</span>
          <span>{sh.stops.length} {sh.stops.length === 1 ? "stop" : "stops"}</span>
        </div>
      </div>
    </section>
  );
}
