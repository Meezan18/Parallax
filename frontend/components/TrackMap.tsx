"use client";

import { useEffect, useMemo, useRef } from "react";
import type { Frame } from "@/lib/types";
import { prefersReducedMotion } from "@/lib/motion";

const W = 1000;
const H = 600;
const PAD = 46;
const TRAIL = 0.035; // fraction of a lap drawn as a trail behind the highlighted cars

type Car = { id: string; color: string; kind: "car" | "focus" | "ghost" | "leader"; label?: string };
type Motion = { from: number; to: number; start: number; dur: number };

/** Generic outline used only if a race has no circuit data. */
function fallbackTrack(): number[][] {
  const pts: number[][] = [];
  for (let i = 0; i < 360; i++) {
    const t = (2 * Math.PI * i) / 360;
    const r = 1 + 0.2 * Math.sin(2 * t) + 0.1 * Math.cos(3 * t);
    pts.push([0.5 + 0.45 * r * Math.cos(t) * 0.75, 0.5 + 0.45 * r * Math.sin(t) * 0.75]);
  }
  return pts;
}

export function TrackMap({ frame, track, secondsPerLap, paused, circuit }: {
  frame: Frame;
  track: number[][] | null | undefined;
  secondsPerLap: number;
  paused: boolean;
  circuit: string;
}) {
  const pts = useMemo(() => {
    const raw = track && track.length > 20 ? track : fallbackTrack();
    const xs = raw.map((p) => p[0]);
    const ys = raw.map((p) => p[1]);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const s = Math.min((W - 2 * PAD) / (maxX - minX || 1), (H - 2 * PAD) / (maxY - minY || 1));
    const ox = (W - (maxX - minX) * s) / 2, oy = (H - (maxY - minY) * s) / 2;
    return raw.map(([x, y]) => [ox + (x - minX) * s, oy + (y - minY) * s]);
  }, [track]);

  const pathD = useMemo(() => "M" + pts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join("L") + "Z", [pts]);

  // where is a car that has covered `progress` laps?
  const pointAt = (progress: number): [number, number] => {
    const f = ((progress % 1) + 1) % 1;
    const x = f * pts.length;
    const i = Math.floor(x) % pts.length;
    const j = (i + 1) % pts.length;
    const k = x - Math.floor(x);
    return [pts[i][0] + (pts[j][0] - pts[i][0]) * k, pts[i][1] + (pts[j][1] - pts[i][1]) * k];
  };

  // ---- targets from the latest frame -------------------------------------
  const { cars, targets } = useMemo(() => {
    const lead = frame.leaderboard[0];
    const refLap = lead?.last_lap && lead.last_lap > 30 ? lead.last_lap : 90;
    const cars: Car[] = [];
    const targets: Record<string, number> = {};
    for (const r of frame.leaderboard) {
      if (r.retired || r.gap_s == null) continue;
      const kind = r.driver === frame.focus.driver ? "focus" : r.position === 1 ? "leader" : "car";
      cars.push({ id: r.driver, color: r.color, kind, label: kind !== "car" ? r.driver : undefined });
      targets[r.driver] = frame.lap - r.gap_s / refLap;
    }
    const sh = frame.focus.shadow;
    if (sh.active && sh.gap_to_leader != null && !sh.retired) {
      cars.push({ id: "__ai", color: "var(--shadow)", kind: "ghost", label: `AI ${frame.focus.driver}` });
      targets.__ai = frame.lap - sh.gap_to_leader / refLap;
    }
    return { cars, targets };
  }, [frame]);

  const motion = useRef<Record<string, Motion>>({});
  const current = useRef<Record<string, number>>({});
  const nodes = useRef<Record<string, SVGGElement | null>>({});
  const trails = useRef<Record<string, SVGPathElement | null>>({});
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  // retarget every car whenever a lap frame arrives
  useEffect(() => {
    const now = performance.now();
    const dur = prefersReducedMotion() ? 0 : Math.max(secondsPerLap, 0.15) * 1000;
    for (const [id, to] of Object.entries(targets)) {
      const from = current.current[id];
      const snap = from == null || Math.abs(to - from) > 2.5 || dur === 0;
      motion.current[id] = { from: snap ? to : from, to, start: now, dur };
      if (snap) current.current[id] = to;
    }
    for (const id of Object.keys(motion.current)) if (!(id in targets)) delete motion.current[id];
  }, [targets, secondsPerLap]);

  // 60fps render loop: writes transforms straight to the DOM, no React re-render per frame
  useEffect(() => {
    let raf = 0;
    let pausedAt: number | null = null;
    const tick = (now: number) => {
      if (pausedRef.current) {
        pausedAt ??= now;
      } else if (pausedAt != null) {
        const shift = now - pausedAt;
        for (const m of Object.values(motion.current)) m.start += shift;
        pausedAt = null;
      }
      const t = pausedAt ?? now;
      for (const [id, m] of Object.entries(motion.current)) {
        const k = m.dur ? Math.min((t - m.start) / m.dur, 1) : 1;
        const p = m.from + (m.to - m.from) * k;
        current.current[id] = p;
        const [x, y] = pointAt(p);
        const g = nodes.current[id];
        if (g) g.setAttribute("transform", `translate(${x.toFixed(1)} ${y.toFixed(1)})`);
        const tr = trails.current[id];
        if (tr) {
          const seg: string[] = [];
          for (let s = 0; s <= 14; s++) {
            const [tx, ty] = pointAt(p - TRAIL + (TRAIL * s) / 14);
            seg.push(`${tx.toFixed(1)},${ty.toFixed(1)}`);
          }
          tr.setAttribute("d", "M" + seg.join("L"));
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pts]);

  const neutral = frame.track_status === "SC" || frame.track_status === "VSC";
  const [sfX, sfY] = pts[0];
  const [nX, nY] = pts[3];
  const ang = (Math.atan2(nY - sfY, nX - sfX) * 180) / Math.PI;
  // background cars first, highlighted ones on top
  const order = [...cars].sort((a, b) => rank(a.kind) - rank(b.kind));

  return (
    <div className={`trackmap${neutral ? " trackmap--neutral" : ""}`}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Live positions on ${circuit}`}>
        <defs>
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="6" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <linearGradient id="trailAi" x1="0" x2="1">
            <stop offset="0" stopColor="#b07cff" stopOpacity="0" />
            <stop offset="1" stopColor="#b07cff" stopOpacity="0.9" />
          </linearGradient>
        </defs>
        <path d={pathD} className="tm-kerb" />
        <path d={pathD} className="tm-asphalt" />
        <path d={pathD} className="tm-line" />
        <g transform={`translate(${sfX} ${sfY}) rotate(${ang + 90})`}>
          <rect x={-13} y={-2.5} width={26} height={5} className="tm-finish" />
        </g>

        {cars.filter((c) => c.kind === "ghost" || c.kind === "focus").map((c) => (
          <path
            key={`trail-${c.id}`}
            ref={(el) => { trails.current[c.id] = el; }}
            className={c.kind === "ghost" ? "tm-trail tm-trail--ai" : "tm-trail"}
            stroke={c.kind === "ghost" ? "url(#trailAi)" : c.color}
          />
        ))}

        {order.map((c) => (
          <g key={c.id} ref={(el) => { nodes.current[c.id] = el; }} className={`tm-car tm-car--${c.kind}`}>
            {c.kind === "ghost" && <circle r={15} className="tm-halo" />}
            <circle r={c.kind === "car" ? 7 : 9.5} fill={c.color} className="tm-dot" filter={c.kind === "ghost" ? "url(#glow)" : undefined} />
            {c.label && (
              <g transform="translate(14 -14)">
                <rect className="tm-tag" x={0} y={-12} rx={4} width={c.label.length * 9 + 14} height={22}
                  style={{ stroke: c.kind === "ghost" ? "var(--shadow)" : c.color }} />
                <text x={7} y={4} className="tm-label">{c.label}</text>
              </g>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}

function rank(k: Car["kind"]) {
  return k === "car" ? 0 : k === "leader" ? 1 : k === "focus" ? 2 : 3;
}
