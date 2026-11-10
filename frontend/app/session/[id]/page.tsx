"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useRaceSession } from "@/lib/useRaceSession";
import { TimingTower } from "@/components/TimingTower";
import { DeltaPanel } from "@/components/DeltaPanel";
import { PaceChart, TyreModelChart } from "@/components/ModelPanels";
import { RadioFeed } from "@/components/RadioFeed";
import { EngineerChat } from "@/components/EngineerChat";
import { signed } from "@/lib/format";

const STATUS_TEXT = { GREEN: "Green", YELLOW: "Yellow", VSC: "Virtual safety car", SC: "Safety car", RED: "Red flag" };

export default function SessionPage() {
  const { id } = useParams<{ id: string }>();
  const s = useRaceSession(id);
  const f = s.latest;

  if (s.status === "error") {
    return (
      <main className="setup" style={{ display: "block" }}>
        <p className="error">{s.error}</p>
        <Link href="/" className="link-btn">Set up a new session</Link>
      </main>
    );
  }

  const startCompound = s.frames[0]?.focus.real.compound ?? "MEDIUM";

  return (
    <div className="dash">
      <header className="topbar">
        <Link href="/" className="brand" style={{ margin: 0, color: "inherit", textDecoration: "none" }}>
          <span className="brand-mark" aria-hidden />
          UNDERCUT
        </Link>
        <span className="event">{s.race?.event ?? "Connecting…"}</span>
        {f && (
          <>
            <span className="lapcount num">
              Lap <b>{f.lap}</b>/{f.total_laps}
            </span>
            <span className={`status-pill status-${f.track_status}`}>{STATUS_TEXT[f.track_status]}</span>
          </>
        )}
        <span className="spacer" />
        {s.session && !s.session.finished && (
          <div className="controls">
            {s.session.paused ? (
              <button className="btn" onClick={s.resume}>Resume</button>
            ) : (
              <button className="btn" onClick={s.pause}>Pause</button>
            )}
            <select
              aria-label="Replay speed"
              value={s.session.seconds_per_lap}
              onChange={(e) => s.setSpeed(Number(e.target.value))}
            >
              <option value={0.5}>0.5s per lap</option>
              <option value={1}>1s per lap</option>
              <option value={2}>2s per lap</option>
              <option value={5}>5s per lap</option>
            </select>
            {f && f.lap + 10 <= f.total_laps && (
              <button className="btn" onClick={() => s.jump(f.lap + 10)}>Skip 10 laps</button>
            )}
          </div>
        )}
        <span className="conn">{s.status === "live" ? "" : "Reconnect by refreshing"}</span>
      </header>

      {!f ? (
        <main className="col" style={{ alignItems: "center", justifyContent: "center" }}>
          <p className="empty">Waiting for lights out…</p>
        </main>
      ) : (
        <main className="grid">
          <aside className="col">
            <TimingTower frame={f} />
          </aside>

          <section className="col">
            {s.summary && (
              <div className="finish" role="status">
                <strong>
                  Chequered flag. AI {s.summary.driver} finished{" "}
                  {s.summary.final_delta == null ? "" : `${signed(-s.summary.final_delta)}s vs the real car, `}
                  P{s.summary.shadow_position ?? "–"} against a real P{s.summary.actual_position ?? "–"}.
                </strong>
                AI stops: {s.summary.shadow_stops.map((x) => `lap ${x.lap} ${x.compound.toLowerCase()}`).join(", ") || "none"}.
                Real stops: {s.summary.actual_stops.map((x) => `lap ${x.lap} ${x.compound.toLowerCase()}`).join(", ") || "none"}.
              </div>
            )}
            <DeltaPanel frames={s.frames} startCompound={startCompound} />
            <div className="chart-row">
              <PaceChart frames={s.frames} />
              <TyreModelChart frame={f} />
            </div>
          </section>

          <aside className="col right">
            <RadioFeed frames={s.frames} />
            <EngineerChat chat={s.chat} onAsk={s.ask} disabled={s.status !== "live"} />
          </aside>
        </main>
      )}
    </div>
  );
}
