"use client";

import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Frame, StopInfo } from "@/lib/types";
import { COMPOUND_HEX, signed } from "@/lib/format";

function Strip({ label, start, stops, total, lap, color }: {
  label: string; start: string; stops: StopInfo[]; total: number; lap: number; color?: string;
}) {
  const segments: { from: number; to: number; compound: string }[] = [];
  let from = 1;
  let compound = start;
  for (const s of stops) {
    segments.push({ from, to: s.lap, compound });
    from = s.lap + 1;
    compound = s.compound;
  }
  segments.push({ from, to: total, compound });
  return (
    <>
      <span style={{ color }}>{label}</span>
      <div className="strip-bar" aria-label={`${label} strategy`}>
        {segments.map((seg, i) => (
          <span
            key={i}
            title={`${seg.compound} laps ${seg.from}–${seg.to}`}
            style={{
              left: `${((seg.from - 1) / total) * 100}%`,
              width: `${((seg.to - seg.from + 1) / total) * 100}%`,
              background: COMPOUND_HEX[seg.compound] ?? "#7d8aa0",
              opacity: seg.from > lap ? 0.25 : 0.9,
            }}
          />
        ))}
        <span className="now" style={{ left: `${(lap / total) * 100}%` }} />
      </div>
    </>
  );
}

export function DeltaPanel({ frames, startCompound }: { frames: Frame[]; startCompound: string }) {
  const f = frames[frames.length - 1];
  const sh = f.focus.shadow;
  const real = f.focus.real;
  const d = sh.delta;
  const cls = d == null || !sh.active || Math.abs(d) < 0.05 ? "even" : d < 0 ? "ahead" : "behind";
  const data = frames.map((x) => ({ lap: x.lap, delta: x.focus.shadow.delta == null ? null : -x.focus.shadow.delta }));
  const plannedStops = sh.pending ? [...sh.stops, sh.pending] : sh.stops;
  const nextPlan = f.plans[0];
  const futureAi = nextPlan ? [...plannedStops, ...nextPlan.stops.filter((s) => !plannedStops.some((p) => p.lap === s.lap))] : plannedStops;

  return (
    <div className="card">
      <div className="delta-hero">
        <div>
          <div className={`delta-number ${cls}`} aria-live="polite">
            {sh.active ? `${signed(d == null ? null : -d)}s` : "±0.0s"}
          </div>
          <div className="delta-caption">
            {!sh.active
              ? "Shadow car is mirroring the real one until the AI takes over."
              : cls === "ahead"
                ? `The AI's ${f.focus.driver} is ahead of the real one.`
                : cls === "behind"
                  ? `The AI's ${f.focus.driver} is behind the real one.`
                  : "Dead level with the real car."}
          </div>
        </div>
        <div className="versus">
          <span />
          <span className="h">Real {f.focus.driver}</span>
          <span className="h ai">AI {f.focus.driver}</span>
          <span className="h">Position</span>
          <span className="v">P{real.position ?? "–"}</span>
          <span className="v ai">P{sh.position ?? "–"}</span>
          <span className="h">Tyres</span>
          <span className="v">{real.compound ? `${real.compound[0]}${real.age}` : "–"}</span>
          <span className="v ai">{sh.compound[0]}{sh.age}</span>
          <span className="h">Stops</span>
          <span className="v">{real.stops.length}</span>
          <span className="v ai">{sh.stops.length}</span>
        </div>
      </div>

      <div style={{ height: 150, marginTop: 16 }}>
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
            <defs>
              <linearGradient id="gainFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#b07cff" stopOpacity={0.45} />
                <stop offset="100%" stopColor="#b07cff" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#36445a" strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="lap" type="number" domain={[1, f.total_laps]} stroke="#8b98ad" fontSize={12} tickLine={false} />
            <YAxis stroke="#8b98ad" fontSize={12} tickLine={false} unit="s" />
            <ReferenceLine y={0} stroke="#8b98ad" />
            <Tooltip
              contentStyle={{ background: "#222c3b", border: "1px solid #36445a", borderRadius: 6 }}
              formatter={(v: number) => [`${signed(v)}s`, "AI gain"]}
              labelFormatter={(l) => `Lap ${l}`}
            />
            <Area type="monotone" dataKey="delta" stroke="#b07cff" strokeWidth={2} fill="url(#gainFill)" connectNulls isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="strip" style={{ marginTop: 12 }}>
        <Strip label="Real" start={startCompound} stops={real.stops} total={f.total_laps} lap={f.lap} />
        <Strip label="AI plan" start={startCompound} stops={futureAi} total={f.total_laps} lap={f.lap} color="var(--shadow)" />
      </div>
    </div>
  );
}
