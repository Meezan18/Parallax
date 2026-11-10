"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Wordmark } from "@/components/Logo";
import type { Compound, EventInfo, RaceSummary, StopInfo } from "@/lib/types";

const YEARS = Array.from({ length: new Date().getFullYear() - 2018 + 1 }, (_, i) => 2018 + i).reverse();
const SPEEDS = [
  { label: "Fast (0.5s per lap)", value: 0.5 },
  { label: "Normal (2s per lap)", value: 2 },
  { label: "Slow (5s per lap)", value: 5 },
];

export default function SetupPage() {
  const router = useRouter();
  const [source, setSource] = useState<"real" | "demo">("real");
  const [year, setYear] = useState(YEARS[1] ?? YEARS[0]);
  const [events, setEvents] = useState<EventInfo[]>([]);
  const [round, setRound] = useState<number | null>(null);
  const [race, setRace] = useState<RaceSummary | null>(null);
  const [driver, setDriver] = useState<string | null>(null);
  const [mode, setMode] = useState<"auto" | "fixed">("auto");
  const [stops, setStops] = useState<StopInfo[]>([{ lap: 20, compound: "HARD" }]);
  const [branch, setBranch] = useState(1);
  const [speed, setSpeed] = useState(2);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (source !== "real") return;
    let cancelled = false;
    setEvents([]);
    setRound(null);
    api
      .schedule(year)
      .then((e) => {
        if (cancelled) return;
        const today = new Date().toISOString().slice(0, 10);
        const past = e.filter((x) => !x.date || x.date < today);
        setEvents(past);
        setRound(past.length ? past[past.length - 1].round : null);
      })
      .catch((err: Error) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [year, source]);

  async function loadRace() {
    setError(null);
    setRace(null);
    setDriver(null);
    setBusy(source === "demo" ? "Generating the simulated race…" : "Downloading timing data. The first load of a race takes about a minute…");
    try {
      const r = await api.loadRace(source === "demo" ? { demo: true } : { year, round: round ?? undefined });
      setRace(r);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function start() {
    if (!race || !driver) return;
    setError(null);
    setBusy("Starting the session…");
    try {
      const s = await api.createSession({
        race_id: race.id,
        driver,
        mode,
        stops: mode === "fixed" ? [...stops].sort((a, b) => a.lap - b.lap) : [],
        branch_lap: branch,
        seconds_per_lap: speed,
      });
      router.push(`/session/${s.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(null);
    }
  }

  const maxLap = race ? race.total_laps - 1 : 70;

  return (
    <main className="setup">
      <section className="pitch">
        <div className="brand">
          <Wordmark size={22} />
        </div>
        <h1>
          The real race.
          <span className="ghost-line">A second car, run by the AI.</span>
        </h1>
        <p>
          Pick a Grand Prix and a driver. Parallax replays the race lap by lap and races a shadow version of that
          driver alongside it, making its own pit calls from what it has seen so far.
        </p>
        <p>
          It learns tyre wear as the race unfolds, calls stops, undercuts and safety-car gambles over the radio, and
          shows exactly how much time a different decision would have won or lost.
        </p>
      </section>

      <section className="panel" aria-label="Session setup">
        <div className="step">
          <h2>Race</h2>
          <p className="hint">
            Real races use FastF1 timing data. The simulated race uses the 2026 grid with invented results and works
            offline.
          </p>
          <div className="segmented" role="group" aria-label="Race source">
            <button aria-pressed={source === "real"} onClick={() => setSource("real")}>Real race</button>
            <button aria-pressed={source === "demo"} onClick={() => setSource("demo")}>Simulated race</button>
          </div>
          {source === "real" && (
            <div className="row" style={{ marginTop: 14 }}>
              <label className="field">
                Season
                <select value={year} onChange={(e) => setYear(Number(e.target.value))} style={{ minWidth: 100 }}>
                  {YEARS.map((y) => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                Grand Prix
                <select value={round ?? ""} onChange={(e) => setRound(Number(e.target.value))} disabled={!events.length}>
                  {!events.length && <option>Loading calendar…</option>}
                  {events.map((ev) => (
                    <option key={ev.round} value={ev.round}>
                      Round {ev.round}: {ev.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}
          <div className="row" style={{ marginTop: 14 }}>
            <button className="btn" onClick={loadRace} disabled={!!busy || (source === "real" && !round)}>
              Load race
            </button>
          </div>
          {race && (
            <p className="loaded">
              {race.event}, {race.total_laps} laps, {race.drivers.length} drivers loaded.
            </p>
          )}
        </div>

        {race && (
          <div className="step">
            <h2>Driver</h2>
            <p className="hint">The AI takes this driver's car and races it against the real one.</p>
            <div className="driver-grid">
              {race.drivers.map((d) => (
                <button key={d.abbr} className="driver-btn" aria-pressed={driver === d.abbr} onClick={() => setDriver(d.abbr)}>
                  <span className="stripe" style={{ background: d.team_color }} />
                  <span style={{ minWidth: 0 }}>
                    <span className="code">{d.abbr}</span>
                    <span className="team" style={{ display: "block" }}>{d.team}</span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {race && driver && (
          <div className="step">
            <h2>Strategy</h2>
            <p className="hint">
              Let the AI call every stop live, or set your own stops and see how they'd have played out.
            </p>
            <div className="segmented" role="group" aria-label="Strategy mode">
              <button aria-pressed={mode === "auto"} onClick={() => setMode("auto")}>AI decides</button>
              <button aria-pressed={mode === "fixed"} onClick={() => setMode("fixed")}>My stops</button>
            </div>

            {mode === "fixed" && (
              <div className="stops">
                {stops.map((s, i) => (
                  <div className="stop-row" key={i}>
                    <label className="field">
                      Box on lap
                      <input
                        type="number" min={Math.max(branch + 1, 2)} max={maxLap} value={s.lap}
                        onChange={(e) => setStops(stops.map((x, j) => (j === i ? { ...x, lap: Number(e.target.value) } : x)))}
                      />
                    </label>
                    <label className="field">
                      Fit
                      <select
                        value={s.compound} style={{ minWidth: 120 }}
                        onChange={(e) => setStops(stops.map((x, j) => (j === i ? { ...x, compound: e.target.value as Compound } : x)))}
                      >
                        <option value="SOFT">Soft</option>
                        <option value="MEDIUM">Medium</option>
                        <option value="HARD">Hard</option>
                      </select>
                    </label>
                    {stops.length > 1 && (
                      <button className="link-btn" onClick={() => setStops(stops.filter((_, j) => j !== i))}>Remove</button>
                    )}
                  </div>
                ))}
                {stops.length < 3 && (
                  <button
                    className="link-btn" style={{ alignSelf: "flex-start" }}
                    onClick={() => setStops([...stops, { lap: Math.min((stops.at(-1)?.lap ?? 20) + 15, maxLap), compound: "MEDIUM" }])}
                  >
                    Add a stop
                  </button>
                )}
              </div>
            )}

            <div className="row" style={{ marginTop: 16 }}>
              <label className="field">
                AI takes over from lap
                <input type="number" min={1} max={maxLap} value={branch} onChange={(e) => setBranch(Number(e.target.value) || 1)} />
              </label>
              <label className="field">
                Replay speed
                <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} style={{ minWidth: 180 }}>
                  {SPEEDS.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </label>
            </div>
          </div>
        )}

        <button className="btn btn-go" onClick={start} disabled={!race || !driver || !!busy}>
          {busy ?? (driver ? `Start the race with ${driver}` : "Start the race")}
        </button>
        {error && <p className="error" role="alert">{error}</p>}
      </section>
    </main>
  );
}
