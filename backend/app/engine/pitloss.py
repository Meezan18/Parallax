"""Estimate the time a pit stop costs at this circuit, from the race itself."""
from __future__ import annotations

from statistics import median

from ..data.schemas import RaceData

DEFAULT_PIT_LOSS = 22.0
NEUTRALISED_FACTOR = {"SC": 0.5, "VSC": 0.65, "RED": 0.0}


def estimate_pit_loss(race: RaceData, up_to_lap: int | None = None) -> float:
    """Median of (in-lap + out-lap) minus two normal laps, over green-flag stops."""
    losses = []
    for laps in race.index().values():
        for n, lap in laps.items():
            nxt = laps.get(n + 1)
            if not lap.pit_in or nxt is None or (up_to_lap is not None and n + 1 > up_to_lap):
                continue
            if lap.lap_time is None or nxt.lap_time is None:
                continue
            if race.track_status(n) != "GREEN" or race.track_status(n + 1) != "GREEN":
                continue
            ref = [l.lap_time for k, l in laps.items()
                   if 0 < abs(k - n) <= 6 and k != n + 1 and l.lap_time
                   and not l.pit_in and not l.pit_out and race.track_status(k) == "GREEN"]
            if len(ref) < 3:
                continue
            losses.append(lap.lap_time + nxt.lap_time - 2 * median(ref))
    if not losses:
        return DEFAULT_PIT_LOSS
    return float(min(max(median(losses), 12.0), 40.0))


def effective_pit_loss(pit_loss: float, status: str) -> float:
    return pit_loss * NEUTRALISED_FACTOR.get(status, 1.0)
