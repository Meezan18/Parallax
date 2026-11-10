"use client";

import { useState } from "react";
import {
  Area, AreaChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { Frame, StopInfo } from "@/lib/types";
import { COMPOUND_HEX, lapTime, signed } from "@/lib/format";

const AXIS = { stroke: "#7d8aa0", fontSize: 12, tickLine: false, axisLine: false } as const;
const GRID = <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />;
const TIP = {
  contentStyle: { background: "rgba(20,27,38,0.96)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, boxShadow: "0 12px 30px rgba(0,0,0,0.4)" },
  labelStyle: { color: "#8b98ad" },
  cursor: { stroke: "rgba(255,255,255,0.15)" },
};

const TABS = ["Gap to real car", "Pace", "Tyre model", "Strategy options"] as const;
type Tab = (typeof TABS)[number];

export function Insights({ frames, startCompound }: { frames: Frame[]; startCompound: string }) {
  const [tab, setTab] = useState<Tab>("Gap to real car");
  return (
    <section className="panel insights">
      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} className="tab" onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>
      <div className="tab-body" role="tabpanel">
        {tab === "Gap to real car" && <GapTrace frames={frames} startCompound={startCompound} />}
        {tab === "Pace" && <Pace frames={frames} />}
        {tab === "Tyre model" && <TyreModel frame={frames[frames.length - 1]} />}
        {tab === "Strategy options" && <Plans frame={frames[frames.length - 1]} />}
      </div>
    </section>
  );
}

function GapTrace({ frames, startCompound }: { frames: Frame[]; startCompound: string }) {
  const f = frames[frames.length - 1];
  const sh = f.focus.shadow;
  const data = frames.map((x) => ({ lap: x.lap, gain: x.focus.shadow.delta == null ? null : -x.focus.shadow.delta }));
  const planned = sh.pending ? [...sh.stops, sh.pending] : sh.stops;
  const future = f.plans[0] ? [...planned, ...f.plans[0].stops.filter((s) => !planned.some((p) => p.lap === s.lap))] : planned;
  return (
    <div className="gap-trace">
      <div className="chart-h">
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -14 }}>
            <defs>
              <linearGradient id="gainUp" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#b07cff" stopOpacity={0.5} />
                <stop offset="100%" stopColor="#b07cff" stopOpacity={0} />
              </linearGradient>
            </defs>
            {GRID}
            <XAxis dataKey="lap" type="number" domain={[1, f.total_laps]} {...AXIS} />
            <YAxis {...AXIS} unit="s" width={52} />
            <ReferenceLine y={0} stroke="rgba(255,255,255,0.25)" />
            <Tooltip {...TIP} formatter={(v: number) => [`${signed(v)}s`, "AI vs real"]} labelFormatter={(l) => `Lap ${l}`} />
            <Area type="monotone" dataKey="gain" stroke="#b07cff" strokeWidth={2.5} fill="url(#gainUp)" connectNulls isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="strips">
        <Strip label="Real" start={startCompound} stops={f.focus.real.stops} total={f.total_laps} lap={f.lap} />
        <Strip label="AI plan" start={startCompound} stops={future} total={f.total_laps} lap={f.lap} ai />
      </div>
    </div>
  );
}

function Strip({ label, start, stops, total, lap, ai }: { label: string; start: string; stops: StopInfo[]; total: number; lap: number; ai?: boolean }) {
  const segs: { from: number; to: number; c: string }[] = [];
  let from = 1;
  let c = start;
  for (const s of stops) {
    segs.push({ from, to: s.lap, c });
    from = s.lap + 1;
    c = s.compound;
  }
  segs.push({ from, to: total, c });
  return (
    <>
      <span className={ai ? "strip-label strip-label--ai" : "strip-label"}>{label}</span>
      <div className="strip">
        {segs.map((s, i) => (
          <span
            key={i}
            title={`${s.c.toLowerCase()} · laps ${s.from}–${s.to}`}
            style={{
              left: `${((s.from - 1) / total) * 100}%`,
              width: `${((s.to - s.from + 1) / total) * 100}%`,
              background: COMPOUND_HEX[s.c] ?? "#7d8aa0",
              opacity: s.from > lap ? 0.28 : 0.95,
            }}
          />
        ))}
        <i style={{ left: `${(lap / total) * 100}%` }} />
      </div>
    </>
  );
}

function Pace({ frames }: { frames: Frame[] }) {
  const data = frames.slice(-24).map((f) => ({
    lap: f.lap,
    real: f.focus.real.lap_time,
    ai: f.focus.shadow.active ? f.focus.shadow.last_lap_time : null,
  }));
  return (
    <div className="chart-h">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -10 }}>
          {GRID}
          <XAxis dataKey="lap" {...AXIS} />
          <YAxis {...AXIS} domain={["dataMin - 0.5", "dataMax + 0.5"]} tickFormatter={(v) => v.toFixed(0)} width={46} />
          <Tooltip {...TIP} labelFormatter={(l) => `Lap ${l}`} formatter={(v: number, n) => [lapTime(v), n === "ai" ? "AI car" : "Real car"]} />
          <Line dataKey="real" stroke="#e6ecf4" dot={false} strokeWidth={2} isAnimationActive={false} />
          <Line dataKey="ai" stroke="#b07cff" dot={false} strokeWidth={2.5} isAnimationActive={false} connectNulls />
        </LineChart>
      </ResponsiveContainer>
      <div className="legend"><span><i style={{ background: "#e6ecf4" }} />Real car</span><span><i style={{ background: "#b07cff" }} />AI car</span></div>
    </div>
  );
}

function TyreModel({ frame }: { frame: Frame }) {
  const curves = frame.model.curves;
  const maxAge = Math.max(...Object.values(curves).map((c) => c.length));
  const data = Array.from({ length: maxAge }, (_, i) => {
    const row: Record<string, number | null> = { age: i + 1 };
    for (const [c, pts] of Object.entries(curves)) row[c] = pts[i]?.time ?? null;
    return row;
  });
  return (
    <div className="tyre-model">
      <div className="chart-h">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -10 }}>
            {GRID}
            <XAxis dataKey="age" {...AXIS} />
            <YAxis {...AXIS} domain={["auto", "auto"]} tickFormatter={(v) => v.toFixed(1)} width={52} />
            <Tooltip {...TIP} labelFormatter={(a) => `Tyre age ${a} laps`} formatter={(v: number, n) => [lapTime(v), String(n).toLowerCase()]} />
            {Object.keys(curves).map((c) => (
              <Line key={c} dataKey={c} stroke={COMPOUND_HEX[c]} dot={false} strokeWidth={2.5} isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <dl className="fits">
        {Object.entries(frame.model.compounds).map(([c, p]) => (
          <div key={c}>
            <dt style={{ color: COMPOUND_HEX[c] }}>{c.charAt(0) + c.slice(1).toLowerCase()}</dt>
            <dd className="num">+{p.deg_per_lap.toFixed(3)}s per lap</dd>
            <dd className="fits-n">{p.laps_observed} laps seen</dd>
          </div>
        ))}
        <div>
          <dt>Pit stop</dt>
          <dd className="num">{frame.model.pit_loss.toFixed(1)}s</dd>
          <dd className="fits-n">refitted from {frame.model.laps_used} laps</dd>
        </div>
      </dl>
    </div>
  );
}

function Plans({ frame }: { frame: Frame }) {
  if (!frame.plans.length) return <p className="empty">No dry-tyre plan to compute this lap.</p>;
  const worst = Math.max(...frame.plans.map((p) => p.delta), 0.1);
  return (
    <ol className="plans">
      {frame.plans.map((p, i) => (
        <li key={p.label} className={i === 0 ? "plan plan--best" : "plan"}>
          <span className="plan-rank">{i === 0 ? "Best" : `+${p.delta.toFixed(1)}s`}</span>
          <span className="plan-label num">{p.label}</span>
          <span className="plan-bar"><i style={{ width: `${100 - (p.delta / worst) * 70}%` }} /></span>
        </li>
      ))}
      {frame.undercut && (
        <li className="plan plan--note">
          Undercut on {frame.undercut.rival}: gap {frame.undercut.gap.toFixed(1)}s, fresh tyres worth about {frame.undercut.gain.toFixed(1)}s.
          {frame.undercut.on ? " It's on." : " Not yet."}
        </li>
      )}
    </ol>
  );
}
