"""The Shadow Race: the same driver, the same race, a different strategy.

Each shadow lap starts from the driver's *real* lap time (which carries traffic,
driver form, safety-car pace, everything the model cannot know) and swaps in only
the tyre effect of the shadow strategy:

    shadow_lap = real_clean_lap + [tyre_model(shadow tyre) - tyre_model(real tyre)] + shadow pit loss

So the delta isolates the strategy call itself. Under SC/VSC tyre effects are
treated as zero and pit stops are cheaper.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..data.schemas import DRY_COMPOUNDS, NEUTRALISED, RaceData
from .degradation import TyreModel
from .pitloss import effective_pit_loss


@dataclass
class ShadowCar:
    driver: str
    compound: str = "UNKNOWN"
    age: int = 0
    used: set = field(default_factory=set)
    race_time: float = 0.0
    pits: list = field(default_factory=list)          # [(lap, compound)]
    pending: Optional[tuple[int, str]] = None         # stop scheduled for (lap, compound)
    fit_next: Optional[str] = None                    # tyres to fit for the next lap
    last_lap_time: Optional[float] = None
    retired: bool = False
    laps_done: int = 0

    def to_dict(self) -> dict:
        return {"compound": self.compound, "age": self.age, "race_time": round(self.race_time, 3),
                "stops": [{"lap": k, "compound": c} for k, c in self.pits],
                "pending": {"lap": self.pending[0], "compound": self.pending[1]} if self.pending else None,
                "last_lap_time": round(self.last_lap_time, 3) if self.last_lap_time else None,
                "retired": self.retired}


class ShadowRace:
    def __init__(self, race: RaceData, driver: str, branch_lap: int = 1):
        self.race = race
        self.driver = driver
        self.laps = race.index()[driver]
        self.branch_lap = max(1, branch_lap)
        first = self.laps.get(1) or self.laps[min(self.laps)]
        self.car = ShadowCar(driver=driver, compound=first.compound, age=max(first.tyre_life - 1, 0),
                             used={first.compound} if first.compound in DRY_COMPOUNDS else set())

    def schedule_pit(self, lap: int, compound: str) -> None:
        self.car.pending = (lap, compound)

    def cancel_pit(self) -> None:
        self.car.pending = None

    def step(self, n: int, model: TyreModel, pit_loss: float) -> Optional[dict]:
        car = self.car
        act = self.laps.get(n)
        if act is None:
            car.retired = car.retired or n <= self.race.total_laps and n > self.race.max_lap(self.driver)
            return None
        status = self.race.track_status(n)

        if n <= self.branch_lap:  # mirror reality until the AI takes over
            car.compound, car.age = act.compound, act.tyre_life
            if act.compound in DRY_COMPOUNDS:
                car.used.add(act.compound)
            if act.pit_out:
                car.pits.append((n - 1, act.compound))
            car.race_time = act.race_time if act.race_time is not None else car.race_time + (act.lap_time or 0)
            car.last_lap_time = act.lap_time
            car.laps_done = n
            if act.pit_in and n == self.branch_lap:
                nxt = self.laps.get(n + 1)
                car.fit_next = nxt.compound if nxt else act.compound
            return {"lap": n, "lap_time": act.lap_time, "pitted": act.pit_in, "mirrored": True}

        if car.fit_next:
            car.compound, car.age = car.fit_next, 1
            if car.fit_next in DRY_COMPOUNDS:
                car.used.add(car.fit_next)
            car.fit_next = None
        else:
            car.age += 1

        act_pred = model.lap_time(act.compound, act.tyre_life, n, self.driver)
        if act.lap_time is None or act.pit_in or act.pit_out:
            clean = act_pred if status not in NEUTRALISED else (self.race.field_median_lap(n) or act_pred)
        else:
            clean = act.lap_time

        tyre_delta = 0.0
        if status not in NEUTRALISED:
            tyre_delta = model.lap_time(car.compound, car.age, n) - model.lap_time(act.compound, act.tyre_life, n)
        lap_time = clean + tyre_delta

        pitted = False
        if car.pending and car.pending[0] == n and n < self.race.total_laps:
            lap_time += effective_pit_loss(pit_loss, status)
            car.pits.append((n, car.pending[1]))
            car.fit_next = car.pending[1]
            pitted = True
        if car.pending and car.pending[0] <= n:
            car.pending = None

        car.race_time += lap_time
        car.last_lap_time = lap_time
        car.laps_done = n
        return {"lap": n, "lap_time": lap_time, "pitted": pitted, "mirrored": False, "tyre_delta": tyre_delta}

    # ---- comparison with reality ----------------------------------------
    def delta(self, n: int) -> Optional[float]:
        act = self.laps.get(n)
        if act is None or act.race_time is None or self.car.laps_done != n:
            return None
        return self.car.race_time - act.race_time

    def virtual_position(self, n: int) -> Optional[int]:
        if self.car.laps_done != n:
            return None
        ahead = 0
        for d, laps in self.race.index().items():
            if d == self.driver:
                continue
            l = laps.get(n)
            if l and l.race_time is not None and l.race_time < self.car.race_time:
                ahead += 1
        return ahead + 1

    def actual_stops(self) -> list[dict]:
        return [{"lap": n, "compound": self.laps[n + 1].compound}
                for n, l in sorted(self.laps.items()) if l.pit_in and (n + 1) in self.laps]
