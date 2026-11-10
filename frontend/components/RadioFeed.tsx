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
  const calls = frames.flatMap((f) => f.calls).reverse();
  return (
    <div>
      <h2 className="section-title">
        Pit wall radio <small>{calls.length} calls</small>
      </h2>
      <div className="radio" aria-live="polite">
        {calls.length === 0 && <p className="empty">Calls appear here once the lights go out.</p>}
        {calls.map((c, i) => (
          <div key={`${c.lap}-${i}`} className={`call ${c.priority} k-${c.kind}`}>
            <div className="meta">
              Lap {c.lap}, {KIND_LABEL[c.kind]}
            </div>
            <div className="msg">{c.message}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
