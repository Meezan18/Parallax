"use client";

import type { BoardRow, Frame } from "@/lib/types";
import { COMPOUND_COLOR, initial, signed } from "@/lib/format";

const ROW = 31;

export function Tyre({ compound, size = 20 }: { compound: string | null; size?: number }) {
  return (
    <span className="tyre" style={{ color: COMPOUND_COLOR[compound ?? "UNKNOWN"], width: size, height: size }} title={compound ?? ""}>
      {initial(compound)}
    </span>
  );
}

type Item = { key: string; ghost: boolean; row?: BoardRow };

/**
 * Rows are absolutely positioned and move with a transform transition, so an overtake
 * slides cars past each other instead of the list re-rendering in a new order.
 */
export function TimingTower({ frame }: { frame: Frame }) {
  const { leaderboard, focus } = frame;
  const sh = focus.shadow;
  const ghostPos = sh.active && sh.position != null && !sh.retired ? sh.position : null;

  const items: Item[] = [];
  let slotted = false;
  for (const r of leaderboard) {
    const realAhead = items.filter((x) => !x.ghost && x.row!.driver !== focus.driver).length;
    if (!slotted && ghostPos != null && realAhead === ghostPos - 1 && r.driver !== focus.driver) {
      items.push({ key: "__ai", ghost: true });
      slotted = true;
    }
    items.push({ key: r.driver, ghost: false, row: r });
  }
  if (!slotted && ghostPos != null) items.push({ key: "__ai", ghost: true });

  // stable DOM order (alphabetical keys) so React never re-mounts rows; only transforms change
  const positions = new Map(items.map((it, i) => [it.key, i]));
  const stable = [...items].sort((a, b) => a.key.localeCompare(b.key));

  return (
    <section className="panel tower-panel" aria-label="Race order">
      <header className="panel-head">
        <h2>Timing</h2>
        <span className="panel-sub">Interval and tyres</span>
      </header>
      <div className="tower" style={{ height: items.length * ROW }} role="table">
        {stable.map((it) => {
          const y = (positions.get(it.key) ?? 0) * ROW;
          if (it.ghost) {
            return (
              <div key={it.key} role="row" className="trow trow--ghost" style={{ transform: `translateY(${y}px)` }}>
                <span className="trow-pos">{ghostPos}</span>
                <span className="trow-stripe" style={{ background: "var(--shadow)" }} />
                <span className="trow-code">AI {focus.driver}</span>
                <span className="trow-gap num">{signed(sh.delta == null ? null : -sh.delta)}s</span>
                <Tyre compound={sh.compound} />
                <span className="trow-age num">{sh.age}</span>
              </div>
            );
          }
          const r = it.row!;
          const cls = ["trow", r.driver === focus.driver && "trow--focus", r.retired && "trow--out", r.in_pit && "trow--pit"]
            .filter(Boolean).join(" ");
          return (
            <div key={it.key} role="row" className={cls} style={{ transform: `translateY(${y}px)` }} title={`${r.name}, ${r.team}`}>
              <span className="trow-pos">{r.position}</span>
              <span className="trow-stripe" style={{ background: r.color }} />
              <span className="trow-code">{r.driver}</span>
              <span className="trow-gap num">{r.retired ? "OUT" : r.in_pit ? "PIT" : r.position === 1 ? "Leader" : r.interval || r.gap}</span>
              <Tyre compound={r.compound} />
              <span className="trow-age num">{r.retired ? "" : r.tyre_age}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
