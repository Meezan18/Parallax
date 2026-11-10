import type { BoardRow, Frame } from "@/lib/types";
import { COMPOUND_COLOR, initial, signed } from "@/lib/format";

function Tyre({ compound }: { compound: string | null }) {
  return (
    <span className="tyre" style={{ color: COMPOUND_COLOR[compound ?? "UNKNOWN"] }} title={compound ?? ""}>
      {initial(compound)}
    </span>
  );
}

export function TimingTower({ frame }: { frame: Frame }) {
  const { leaderboard, focus } = frame;
  const sh = focus.shadow;
  const ghostPos = sh.active && sh.position != null ? sh.position : null;

  const rows: (BoardRow | "ghost")[] = [];
  let slotted = false;
  const others = leaderboard; // the real car stays in; the ghost slots in at its virtual position
  others.forEach((r) => {
    const othersAhead = rows.filter((x) => x !== "ghost" && (x as BoardRow).driver !== focus.driver).length;
    if (!slotted && ghostPos != null && othersAhead === ghostPos - 1 && r.driver !== focus.driver) {
      rows.push("ghost");
      slotted = true;
    }
    rows.push(r);
  });
  if (!slotted && ghostPos != null) rows.push("ghost");

  return (
    <div>
      <h2 className="section-title">
        Timing <small>purple row: AI car, gain vs real</small>
      </h2>
      <div className="tower" role="table" aria-label="Race order">
        {rows.map((r) =>
          r === "ghost" ? (
            <div className="tower-row ghost" role="row" key="ghost">
              <span className="pos">{ghostPos}</span>
              <span className="stripe" style={{ background: "var(--shadow)" }} />
              <span className="code">AI</span>
              <span className="gap num" title="Time gained (+) or lost (−) against the real car">{signed(sh.delta == null ? null : -sh.delta)}</span>
              <Tyre compound={sh.compound} />
              <span className="tyre-age num">{sh.age}</span>
            </div>
          ) : (
            <div
              key={r.driver}
              role="row"
              className={`tower-row${r.driver === focus.driver ? " focus" : ""}${r.retired ? " out" : ""}`}
              title={`${r.name}, ${r.team}`}
            >
              <span className="pos">{r.position}</span>
              <span className="stripe" style={{ background: r.color }} />
              <span className="code">{r.driver}</span>
              <span className="gap num">{r.in_pit ? "PIT" : r.interval || r.gap}</span>
              <Tyre compound={r.compound} />
              <span className="tyre-age num">{r.retired ? "" : r.tyre_age}</span>
            </div>
          ),
        )}
      </div>
    </div>
  );
}
