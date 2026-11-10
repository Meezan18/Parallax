"""Normalized race data shared by every part of the engine.

Everything downstream (tyre model, optimizer, shadow race, API) works on these
plain dataclasses, never on FastF1 DataFrames. That keeps the engine testable
with synthetic data and independent of the data source.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Optional

DRY_COMPOUNDS = ("SOFT", "MEDIUM", "HARD")
STATUS_SEVERITY = {"GREEN": 0, "YELLOW": 1, "VSC": 2, "SC": 3, "RED": 4}
NEUTRALISED = ("SC", "VSC", "RED")


@dataclass
class Lap:
    driver: str
    lap: int
    lap_time: Optional[float]      # seconds
    compound: str                  # SOFT / MEDIUM / HARD / INTERMEDIATE / WET / UNKNOWN
    tyre_life: int                 # laps on this set, including this lap
    stint: int
    pit_in: bool                   # car entered the pit lane at the end of this lap
    pit_out: bool                  # car left the pit lane at the start of this lap
    position: Optional[int]
    track_status: str              # GREEN / YELLOW / VSC / SC / RED
    race_time: Optional[float]     # seconds since race start when this lap ended

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class Driver:
    abbr: str
    full_name: str
    team: str
    team_color: str = "#888888"
    number: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class RaceData:
    year: int
    round: int
    event: str
    circuit: str
    total_laps: int
    drivers: list[Driver]
    laps: list[Lap]
    source: str = "fastf1"
    race_id: Optional[int] = None
    track: Optional[list[list[float]]] = None   # circuit outline, normalised to 0..1, starts at the finish line
    _index: Optional[dict] = field(default=None, init=False, repr=False, compare=False)
    _status: Optional[dict] = field(default=None, init=False, repr=False, compare=False)
    _field_median: dict = field(default_factory=dict, init=False, repr=False, compare=False)

    # ---- lookups -------------------------------------------------------
    def index(self) -> dict[str, dict[int, Lap]]:
        """driver -> lap number -> Lap"""
        if self._index is None:
            idx: dict[str, dict[int, Lap]] = {}
            for lap in self.laps:
                idx.setdefault(lap.driver, {})[lap.lap] = lap
            self._index = idx
        return self._index

    def driver(self, abbr: str) -> Optional[Driver]:
        abbr = abbr.upper()
        return next((d for d in self.drivers if d.abbr == abbr), None)

    def track_status(self, lap: int) -> str:
        """Most severe status reported by any car on that lap."""
        if self._status is None:
            status: dict[int, str] = {}
            for l in self.laps:
                cur = status.get(l.lap, "GREEN")
                if STATUS_SEVERITY.get(l.track_status, 0) > STATUS_SEVERITY[cur]:
                    cur = l.track_status
                status[l.lap] = cur
            self._status = status
        return self._status.get(lap, "GREEN")

    def field_median_lap(self, lap: int) -> Optional[float]:
        """Median lap time of cars that did not pit on this lap."""
        if lap not in self._field_median:
            times = [l.lap_time for l in self.laps
                     if l.lap == lap and l.lap_time and not l.pit_in and not l.pit_out]
            self._field_median[lap] = median(times) if times else None
        return self._field_median[lap]

    def max_lap(self, driver: str) -> int:
        laps = self.index().get(driver, {})
        return max(laps) if laps else 0

    def summary(self) -> dict:
        return {
            "id": self.race_id,
            "year": self.year,
            "round": self.round,
            "event": self.event,
            "circuit": self.circuit,
            "total_laps": self.total_laps,
            "source": self.source,
            "drivers": [d.to_dict() for d in self.drivers],
            "track": self.track,
        }


def normalise_track(xs: list[float], ys: list[float], points: int = 360) -> list[list[float]]:
    """Resample a closed outline to evenly spaced points and fit it into a unit box."""
    import numpy as np

    x, y = np.asarray(xs, float), np.asarray(ys, float)
    if x[0] != x[-1] or y[0] != y[-1]:
        x, y = np.append(x, x[0]), np.append(y, y[0])
    seg = np.hypot(np.diff(x), np.diff(y))
    dist = np.concatenate([[0.0], np.cumsum(seg)])
    target = np.linspace(0, dist[-1], points, endpoint=False)
    rx, ry = np.interp(target, dist, x), np.interp(target, dist, y)
    span = max(rx.max() - rx.min(), ry.max() - ry.min()) or 1.0
    rx = (rx - rx.min()) / span
    ry = (ry - ry.min()) / span
    # centre within the unit box, flip y so north is up on screen
    rx += (1 - (rx.max() - rx.min())) / 2
    ry = 1 - ry
    ry -= (ry.min() - (1 - (ry.max() - ry.min())) / 2)
    return [[round(float(a), 4), round(float(b), 4)] for a, b in zip(rx, ry)]
