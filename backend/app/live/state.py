"""Race snapshot at a given moment: who is where, on what tyres, with what gaps."""
from __future__ import annotations

from ..data.schemas import RaceData


def leaderboard(race: RaceData, lap: int) -> list[dict]:
    """Snapshot at the moment the leader completes `lap`.

    Every car shows its latest completed lap at that moment. Gaps are measured at
    the timing line: a car's time at its latest lap minus the first car's time at
    that same lap. That handles cars that are a few seconds behind (still on the
    previous lap at this instant), lapped cars and retirements.
    """
    idx = race.index()
    first_at: dict[int, float] = {}
    for laps in idx.values():
        for k, l in laps.items():
            if l.race_time is not None and (k not in first_at or l.race_time < first_at[k]):
                first_at[k] = l.race_time
    if lap not in first_at:
        return []
    t = first_at[lap]

    rows = []
    for d in race.drivers:
        laps = idx.get(d.abbr)
        if not laps:
            continue
        done = [k for k, l in laps.items() if l.race_time is not None and l.race_time <= t + 1e-6]
        if not done:
            continue
        k = max(done)
        l = laps[k]
        gap = l.race_time - first_at[k]
        laps_down = sum(1 for m, rt in first_at.items() if m > k and rt < l.race_time)
        retired = (k + 1) not in laps and k < race.total_laps - 5 and t - l.race_time > 150
        rows.append({"driver": d.abbr, "name": d.full_name, "team": d.team, "color": d.team_color,
                     "laps": k, "race_time": round(l.race_time, 3), "compound": l.compound,
                     "tyre_age": l.tyre_life, "stops": max(l.stint - 1, 0),
                     "last_lap": round(l.lap_time, 3) if l.lap_time else None, "in_pit": l.pit_in,
                     "retired": retired, "laps_down": laps_down, "gap_s": round(gap, 3)})

    rows.sort(key=lambda r: (r["retired"], r["laps_down"], r["gap_s"]))
    prev = None
    for pos, r in enumerate(rows, start=1):
        r["position"] = pos
        if r["retired"]:
            r["gap"], r["interval"], r["gap_s"] = "OUT", "OUT", None
            continue
        if r["laps_down"]:
            r["gap"] = f"+{r['laps_down']} LAP" + ("S" if r["laps_down"] > 1 else "")
        else:
            r["gap"] = "LEADER" if prev is None else f"+{r['gap_s']:.1f}"
        r["interval"] = "" if prev is None else f"+{max(r['gap_s'] - prev['gap_s'], 0):.1f}"
        prev = r
    return rows
