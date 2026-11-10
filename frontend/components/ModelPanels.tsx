"use client";

import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Frame } from "@/lib/types";
import { COMPOUND_HEX, lapTime } from "@/lib/format";

const tooltipStyle = { background: "#222c3b", border: "1px solid #36445a", borderRadius: 6 };

export function TyreModelChart({ frame }: { frame: Frame }) {
  const curves = frame.model.curves;
  const maxAge = Math.max(...Object.values(curves).map((c) => c.length));
  const data = Array.from({ length: maxAge }, (_, i) => {
    const row: Record<string, number | null> = { age: i + 1 };
    for (const [c, pts] of Object.entries(curves)) row[c] = pts[i]?.time ?? null;
    return row;
  });
  const fits = frame.model.compounds;
  return (
    <div className="card">
      <h3 className="section-title">
        Tyre model <small>refitted every lap from {frame.model.laps_used} clean laps</small>
      </h3>
      <div style={{ height: 170 }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -10 }}>
            <CartesianGrid stroke="#36445a" strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="age" stroke="#8b98ad" fontSize={12} tickLine={false} />
            <YAxis stroke="#8b98ad" fontSize={12} tickLine={false} domain={["auto", "auto"]} tickFormatter={(v) => v.toFixed(1)} width={52} />
            <Tooltip contentStyle={tooltipStyle} labelFormatter={(a) => `Tyre age ${a} laps`} formatter={(v: number, n) => [lapTime(v), n]} />
            {Object.keys(curves).map((c) => (
              <Line key={c} dataKey={c} stroke={COMPOUND_HEX[c]} dot={false} strokeWidth={2} isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="plans" style={{ marginTop: 8 }}>
        {Object.entries(fits).map(([c, p]) => (
          <div key={c} style={{ color: COMPOUND_HEX[c] }}>
            <span>{c.charAt(0) + c.slice(1).toLowerCase()}</span>
            <span className="num">+{p.deg_per_lap.toFixed(3)}s/lap, {p.laps_observed} laps seen</span>
          </div>
        ))}
        <div style={{ color: "var(--muted)" }}>
          <span>Pit stop costs</span>
          <span className="num">{frame.model.pit_loss.toFixed(1)}s</span>
        </div>
      </div>
    </div>
  );
}

export function PaceChart({ frames }: { frames: Frame[] }) {
  const recent = frames.slice(-20).map((f) => ({
    lap: f.lap,
    real: f.focus.real.lap_time,
    ai: f.focus.shadow.active ? f.focus.shadow.last_lap_time : null,
  }));
  const plans = frames[frames.length - 1].plans;
  return (
    <div className="card">
      <h3 className="section-title">
        Pace <small>last 20 laps</small>
      </h3>
      <div style={{ height: 170 }}>
        <ResponsiveContainer>
          <LineChart data={recent} margin={{ top: 4, right: 8, bottom: 0, left: -10 }}>
            <CartesianGrid stroke="#36445a" strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="lap" stroke="#8b98ad" fontSize={12} tickLine={false} />
            <YAxis stroke="#8b98ad" fontSize={12} tickLine={false} domain={["dataMin - 0.5", "dataMax + 0.5"]} tickFormatter={(v) => v.toFixed(0)} width={46} />
            <Tooltip contentStyle={tooltipStyle} labelFormatter={(l) => `Lap ${l}`} formatter={(v: number, n) => [lapTime(v), n === "ai" ? "AI" : "Real"]} />
            <Legend formatter={(v) => (v === "ai" ? "AI car" : "Real car")} wrapperStyle={{ fontSize: 12 }} />
            <Line dataKey="real" stroke="#e6ecf4" dot={false} strokeWidth={2} isAnimationActive={false} />
            <Line dataKey="ai" stroke="#b07cff" dot={false} strokeWidth={2} isAnimationActive={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="plans" style={{ marginTop: 8 }}>
        {plans.length ? (
          plans.map((p, i) => (
            <div key={p.label}>
              <span>{i === 0 ? "Best plan" : `Option ${i + 1}`}</span>
              <span className="num">{p.label}{i ? `  +${p.delta.toFixed(1)}s` : ""}</span>
            </div>
          ))
        ) : (
          <span className="empty">No plan to compute this lap.</span>
        )}
      </div>
    </div>
  );
}
