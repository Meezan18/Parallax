"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useRaceSession } from "@/lib/useRaceSession";
import { TimingTower } from "@/components/TimingTower";
import { TrackMap } from "@/components/TrackMap";
import { DuelBar } from "@/components/DuelBar";
import { Insights } from "@/components/Insights";
import { BoxAlert } from "@/components/BoxAlert";
import { RadioFeed } from "@/components/RadioFeed";
import { EngineerChat } from "@/components/EngineerChat";
import { ParallaxMark, Wordmark } from "@/components/Logo";

const STATUS_TEXT = { GREEN: "Green flag", YELLOW: "Yellow flag", VSC: "Virtual safety car", SC: "Safety car", RED: "Red flag" };

export default function SessionPage() {
  const { id } = useParams<{ id: string }>();
  const s = useRaceSession(id);
  const f = s.latest;

  if (s.status === "error") {
    return (
      <main className="center-state">
        <ParallaxMark size={56} />
        <p className="error">{s.error}</p>
        <Link href="/" className="btn">Set up a new session</Link>
      </main>
    );
  }

  const startCompound = s.frames[0]?.focus.real.compound ?? "MEDIUM";
  const focusDriver = s.race?.drivers.find((d) => d.abbr === s.session?.driver);
  const pct = f ? (f.lap / f.total_laps) * 100 : 0;
  const speed = s.session?.seconds_per_lap ?? 2;

  return (
    <div className="dash">
      <header className="hud">
        <Link href="/" className="px-brand" aria-label="Parallax home">
          <Wordmark size={19} />
        </Link>
        <div className="hud-event">
          <span className="hud-title">{s.race?.event ?? "Connecting…"}</span>
          {s.race?.source === "synthetic" && (
            <span className="sim-note" title="Real 2026 driver and team names; the race and its results are invented">Simulated</span>
          )}
        </div>
        {f && (
          <div className="hud-lap">
            <span className="hud-lap-label">Lap</span>
            <span className="hud-lap-n num">{f.lap}</span>
            <span className="hud-lap-t num">/{f.total_laps}</span>
          </div>
        )}
        {f && <span className={`flag flag--${f.track_status}`}>{STATUS_TEXT[f.track_status]}</span>}
        <span className="hud-spacer" />
        {s.session && !s.session.finished && f && (
          <div className="hud-controls">
            <button className="ctl" onClick={s.session.paused ? s.resume : s.pause} aria-label={s.session.paused ? "Resume" : "Pause"}>
              {s.session.paused ? (
                <svg viewBox="0 0 16 16" width="14" height="14"><path d="M4 2.5v11l9-5.5z" fill="currentColor" /></svg>
              ) : (
                <svg viewBox="0 0 16 16" width="14" height="14"><path d="M4 2.5h3v11H4zM9 2.5h3v11H9z" fill="currentColor" /></svg>
              )}
            </button>
            <div className="speed" role="group" aria-label="Replay speed">
              {[0.5, 1, 2, 5].map((v) => (
                <button key={v} aria-pressed={speed === v} onClick={() => s.setSpeed(v)}>
                  {v < 1 ? "4×" : v === 1 ? "2×" : v === 2 ? "1×" : "½×"}
                </button>
              ))}
            </div>
            {f.lap + 10 <= f.total_laps && (
              <button className="ctl ctl--text" onClick={() => s.jump(f.lap + 10)}>+10 laps</button>
            )}
          </div>
        )}
        <div className="hud-progress" aria-hidden><i style={{ width: `${pct}%`, transitionDuration: `${speed}s` }} /></div>
      </header>

      {!f ? (
        <main className="center-state" role="status">
          <ParallaxMark size={72} motion="loop" title="Loading" />
          <p>Waiting for lights out…</p>
        </main>
      ) : (
        <main className="board">
          <TimingTower frame={f} />

          <div className="stage">
            {s.summary && (
              <div className="finish" role="status">
                <span className="finish-flag" aria-hidden />
                <div>
                  <strong>
                    {s.summary.retired
                      ? `Real ${s.summary.driver} retired after lap ${s.summary.last_lap ?? "?"}.`
                      : `Chequered flag. AI ${s.summary.driver} finishes P${s.summary.shadow_position ?? "–"}, the real car P${s.summary.actual_position ?? "–"}.`}
                  </strong>
                  <span>
                    AI stops: {s.summary.shadow_stops.map((x) => `lap ${x.lap} ${x.compound.toLowerCase()}`).join(", ") || "none"}.
                    {" "}Real stops: {s.summary.actual_stops.map((x) => `lap ${x.lap} ${x.compound.toLowerCase()}`).join(", ") || "none"}.
                  </span>
                </div>
              </div>
            )}
            <section className="panel track-panel">
              <header className="panel-head panel-head--float">
                <h2>{s.race?.circuit ?? "Circuit"}</h2>
                <span className="legend">
                  <span><i className="lg-ai" />AI car</span>
                  <span><i style={{ background: focusDriver?.team_color ?? "#fff" }} />Real {f.focus.driver}</span>
                </span>
              </header>
              <TrackMap frame={f} track={s.race?.track} secondsPerLap={speed} paused={!!s.session?.paused} circuit={s.race?.circuit ?? "the circuit"} />
              <BoxAlert frame={f} />
            </section>
            <DuelBar frames={s.frames} teamColor={focusDriver?.team_color ?? "#e6ecf4"} />
            <Insights frames={s.frames} startCompound={startCompound} />
          </div>

          <div className="side">
            <RadioFeed frames={s.frames} />
            <EngineerChat chat={s.chat} onAsk={s.ask} disabled={s.status !== "live"} />
          </div>
        </main>
      )}
    </div>
  );
}
