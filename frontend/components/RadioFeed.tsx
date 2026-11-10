import type { Call, Frame } from "@/lib/types";

const KIND_LABEL: Record<Call["kind"], string> = {
  BOX: "Box call",
  SC_BOX: "Cheap stop",
  WINDOW: "Pit window",
  STAY_OUT: "Stay out",
  PLAN: "Plan change",
  UNDERCUT: "Undercut",
  THREAT: "Threat",
  RACE: "Race control",
  INFO: "Info",
};

export function RadioFeed({ frames }: { frames: Frame[] }) {
  const calls = frames.flatMap((f) => f.calls.map((c, i) => ({ ...c, key: `${f.lap}-${i}-${c.kind}` }))).reverse();
  return (
    <section className="panel radio-panel" aria-label="Pit wall radio">
      <header className="panel-head">
        <h2>
          <span className="live-dot" aria-hidden />
          Pit wall radio
        </h2>
        <span className="panel-sub">{calls.length} calls</span>
      </header>
      <div className="radio" aria-live="polite">
        {calls.length === 0 && <p className="empty">Calls appear here once the lights go out.</p>}
        {calls.map((c) => (
          <article key={c.key} className={`call call--${c.kind} call--${c.priority}`}>
            <div className="call-meta">
              <span className="call-kind">{KIND_LABEL[c.kind]}</span>
              <span className="num">Lap {c.lap}</span>
            </div>
            <p className="call-msg">{c.message}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
