"""Enumerate every legal 0/1/2-stop plan for the rest of the race and rank them.

Stint costs come from closed-form cumulative sums, and the 2-stop search is
vectorised with numpy, so a full re-plan takes a few milliseconds and can run
every lap.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..data.schemas import DRY_COMPOUNDS
from .degradation import TyreModel

INITIAL = {"SOFT": "S", "MEDIUM": "M", "HARD": "H", "INTERMEDIATE": "I", "WET": "W"}


@dataclass
class Plan:
    stops: list[tuple[int, str]]        # (pit lap, compound fitted)
    time: float                         # predicted time for remaining laps (excl. fuel), incl. pit loss
    start_compound: str = ""
    delta: float = 0.0                  # vs best plan
    _key: tuple = field(default=(), repr=False)

    @property
    def next_stop(self) -> tuple[int, str] | None:
        return self.stops[0] if self.stops else None

    def label(self) -> str:
        chain = "-".join([INITIAL.get(self.start_compound, "?")] + [INITIAL.get(c, "?") for _, c in self.stops])
        laps = ", ".join(f"L{k}" for k, _ in self.stops)
        return f"{chain} ({laps})" if laps else f"{chain} (no stop)"

    def to_dict(self) -> dict:
        return {"label": self.label(), "stops": [{"lap": k, "compound": c} for k, c in self.stops],
                "time": round(self.time, 2), "delta": round(self.delta, 2)}


def _rule_ok(used: set[str], *compounds: str) -> bool:
    """Dry races require two different dry compounds."""
    return len((used | set(compounds)) & set(DRY_COMPOUNDS)) >= 2


def best_plans(model: TyreModel, driver: str | None, current_lap: int, compound: str, age: int,
               used: set[str], pit_loss: float, immediate_pit_loss: float | None = None,
               max_stops: int = 2, top: int = 5, min_stint: int = 3, _relaxed: bool = False) -> list[Plan]:
    """current_lap = last completed lap; a stop on lap k means new tyres from lap k+1."""
    T = model.total_laps
    R = T - current_lap
    if R <= 0 or compound not in DRY_COMPOUNDS:
        return []

    stretch = 1.5 if _relaxed else 1.0
    def max_len(c: str) -> int:
        return int(model.max_stint(c) * stretch)

    def loss_at(k: int) -> float:
        return immediate_pit_loss if (immediate_pit_loss is not None and k == current_lap + 1) else pit_loss

    cur = model.stint_costs(compound, age + 1, R, driver)
    new = {c: model.stint_costs(c, 1, R, driver) for c in DRY_COMPOUNDS}
    cur_limit = max(1, max_len(compound) - age)
    plans: list[Plan] = []

    if R <= cur_limit and _rule_ok(used, compound):
        plans.append(Plan([], float(cur[R])))

    for c2 in DRY_COMPOUNDS:
        if not _rule_ok(used, compound, c2):
            continue
        for n1 in range(1, min(cur_limit, R - min_stint) + 1):
            n2 = R - n1
            if n2 > max_len(c2):
                continue
            k = current_lap + n1
            plans.append(Plan([(k, c2)], float(cur[n1] + new[c2][n2] + loss_at(k))))

    if max_stops >= 2:
        for c2 in DRY_COMPOUNDS:
            for c3 in DRY_COMPOUNDS:
                if not _rule_ok(used, compound, c2, c3):
                    continue
                for n1 in range(1, min(cur_limit, R - 2 * min_stint) + 1):
                    n2s = np.arange(min_stint, min(max_len(c2), R - n1 - min_stint) + 1)
                    if len(n2s) == 0:
                        continue
                    n3s = R - n1 - n2s
                    valid = n3s <= max_len(c3)
                    if not valid.any():
                        continue
                    n2s, n3s = n2s[valid], n3s[valid]
                    k1 = current_lap + n1
                    costs = cur[n1] + new[c2][n2s] + new[c3][n3s] + loss_at(k1) + pit_loss
                    j = int(np.argmin(costs))
                    k2 = k1 + int(n2s[j])
                    plans.append(Plan([(k1, c2), (k2, c3)], float(costs[j])))

    if not plans:
        if not _relaxed:
            return best_plans(model, driver, current_lap, compound, age, used, pit_loss,
                              immediate_pit_loss, max_stops, top, 1, _relaxed=True)
        return []

    plans.sort(key=lambda p: p.time)
    best = plans[0].time
    out, seen = [], set()
    for p in plans:
        key = (tuple(c for _, c in p.stops), p.stops[0][0] if p.stops else None)
        if key in seen:
            continue
        seen.add(key)
        p.start_compound = compound
        p.delta = p.time - best
        out.append(p)
        if len(out) >= top:
            break
    return out


def evaluate_plan(model: TyreModel, driver: str | None, current_lap: int, compound: str, age: int,
                  stops: list[tuple[int, str]], pit_loss: float) -> float:
    """Predicted time of a given plan, on the same basis as best_plans."""
    total, lap, comp, a = 0.0, current_lap, compound, age
    for k, c in sorted(stops) + [(model.total_laps, None)]:
        n = k - lap
        if n > 0:
            total += float(model.stint_costs(comp, a + 1, n, driver)[n])
        if c is not None:
            total += pit_loss
            comp, a = c, 0
        else:
            a += n
        lap = k
    return total
