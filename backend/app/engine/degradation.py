"""Tyre degradation model, refitted live as the race unfolds.

Lap time model (fuel corrected):

    lap_time = intercept[c] + driver_offset[d] + b[c]*age + k[c]*age^2 + fuel*(laps_remaining)

It is fitted by ridge regression that shrinks towards physical priors. Early in the
race, with few clean laps, the priors dominate; as laps arrive the data takes over.
A compound nobody has run yet keeps its prior shape, anchored to the best-observed
compound. That is the "learns degradation lap by lap" behaviour of the pit wall.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median

import numpy as np

from ..data.schemas import DRY_COMPOUNDS, RaceData

FUEL_PER_LAP = 0.032  # s of lap time per lap of fuel carried (~0.03 s/kg * ~1.1 kg/lap)

PRIORS = {
    "SOFT": {"offset": -0.6, "b": 0.080, "k": 0.0010, "max_stint": 25},
    "MEDIUM": {"offset": 0.0, "b": 0.050, "k": 0.0005, "max_stint": 36},
    "HARD": {"offset": 0.5, "b": 0.030, "k": 0.0002, "max_stint": 50},
}
LAMBDA_INTERCEPT = 1.0
LAMBDA_SLOPE = 40.0
LAMBDA_DRIVER = 8.0
MIN_LAPS_FOR_OWN_INTERCEPT = 8
AGE_SCALE = 10.0  # ages are scaled to keep the ridge penalty well conditioned


@dataclass
class CompoundParams:
    intercept: float
    b: float
    k: float
    n_laps: int
    max_stint: int

    def to_dict(self) -> dict:
        return {"intercept": round(self.intercept, 3), "deg_per_lap": round(self.b, 4),
                "deg_quadratic": round(self.k, 5), "laps_observed": self.n_laps, "max_stint": self.max_stint}


class TyreModel:
    def __init__(self, total_laps: int, params: dict[str, CompoundParams], driver_offset: dict[str, float],
                 residual_sd: float, n_laps: int, fuel: float = FUEL_PER_LAP):
        self.total_laps = total_laps
        self.params = params
        self.driver_offset = driver_offset
        self.residual_sd = residual_sd
        self.n_laps = n_laps
        self.fuel = fuel

    # ---- fitting -------------------------------------------------------
    @staticmethod
    def clean_laps(race: RaceData, up_to_lap: int | None = None) -> list:
        rows = []
        for laps in race.index().values():
            ok = [l for l in laps.values()
                  if l.lap >= 2 and l.lap_time and l.track_status == "GREEN"
                  and race.track_status(l.lap - 1) == "GREEN"          # skip restart laps
                  and not l.pit_in and not l.pit_out
                  and l.compound in DRY_COMPOUNDS and l.tyre_life >= 1
                  and (up_to_lap is None or l.lap <= up_to_lap)]
            if not ok:
                continue
            med = median(l.lap_time for l in ok)
            rows.extend(l for l in ok if 0.97 * med <= l.lap_time <= 1.035 * med)  # drop traffic/mistakes
        return rows

    @classmethod
    def fit(cls, race: RaceData, up_to_lap: int | None = None) -> "TyreModel":
        rows = cls.clean_laps(race, up_to_lap)
        T = race.total_laps
        comps = list(DRY_COMPOUNDS)
        nc = len(comps)
        drivers = sorted({r.driver for r in rows})
        d_index = {d: i for i, d in enumerate(drivers)}
        ncol = 3 * nc + len(drivers)

        y = np.array([r.lap_time - FUEL_PER_LAP * (T - r.lap) for r in rows], dtype=float)
        X = np.zeros((len(rows), ncol))
        for i, r in enumerate(rows):
            ci = comps.index(r.compound)
            a = r.tyre_life / AGE_SCALE
            X[i, ci] = 1.0
            X[i, nc + ci] = a
            X[i, 2 * nc + ci] = a * a
            X[i, 3 * nc + d_index[r.driver]] = 1.0

        base = float(np.median(y)) if len(y) else 90.0
        w0 = np.zeros(ncol)
        lam = np.full(ncol, LAMBDA_DRIVER)
        for ci, c in enumerate(comps):
            p = PRIORS[c]
            w0[ci] = base + p["offset"] - 0.6       # intercept is at age 0, median is mid-stint
            lam[ci] = LAMBDA_INTERCEPT
            w0[nc + ci] = p["b"] * AGE_SCALE
            lam[nc + ci] = LAMBDA_SLOPE
            w0[2 * nc + ci] = p["k"] * AGE_SCALE ** 2
            lam[2 * nc + ci] = LAMBDA_SLOPE

        A = X.T @ X + np.diag(lam)
        w = np.linalg.solve(A, X.T @ y + lam * w0)
        resid = y - X @ w if len(y) else np.array([0.3])

        counts = {c: sum(1 for r in rows if r.compound == c) for c in comps}
        observed_life = {c: max((r.tyre_life for r in rows if r.compound == c), default=0) for c in comps}
        params = {}
        for ci, c in enumerate(comps):
            params[c] = CompoundParams(
                intercept=float(w[ci]),
                b=max(float(w[nc + ci]) / AGE_SCALE, 0.005),
                k=max(float(w[2 * nc + ci]) / AGE_SCALE ** 2, 0.0),
                n_laps=counts[c],
                max_stint=max(PRIORS[c]["max_stint"], observed_life[c] + 3),
            )
        # anchor sparsely observed compounds to the best observed one using prior offsets
        ref = max(comps, key=lambda c: counts[c])
        if counts[ref] >= MIN_LAPS_FOR_OWN_INTERCEPT:
            for c in comps:
                if counts[c] < MIN_LAPS_FOR_OWN_INTERCEPT:
                    params[c].intercept = params[ref].intercept + PRIORS[c]["offset"] - PRIORS[ref]["offset"]

        offsets = {d: float(w[3 * nc + i]) for d, i in d_index.items()}
        return cls(T, params, offsets, float(np.std(resid)) if len(resid) > 1 else 0.3, len(rows))

    # ---- prediction ----------------------------------------------------
    def _p(self, compound: str) -> CompoundParams:
        return self.params.get(compound) or self.params["MEDIUM"]

    def max_stint(self, compound: str) -> int:
        return self._p(compound).max_stint

    def tyre_time(self, compound: str, age: float) -> float:
        p = self._p(compound)
        return p.intercept + p.b * age + p.k * age * age

    def lap_time(self, compound: str, age: float, lap: int, driver: str | None = None) -> float:
        return (self.tyre_time(compound, age) + self.fuel * (self.total_laps - lap)
                + (self.driver_offset.get(driver, 0.0) if driver else 0.0))

    def stint_costs(self, compound: str, start_age: int, n_max: int, driver: str | None = None) -> np.ndarray:
        """cum[n] = summed lap time (no fuel term) for n laps starting at tyre age start_age."""
        ages = np.arange(start_age, start_age + max(n_max, 0), dtype=float)
        p = self._p(compound)
        per_lap = p.intercept + p.b * ages + p.k * ages ** 2 + (self.driver_offset.get(driver, 0.0) if driver else 0.0)
        return np.concatenate([[0.0], np.cumsum(per_lap)])

    def curves(self) -> dict[str, list[dict]]:
        mid_fuel = self.fuel * self.total_laps / 2
        return {c: [{"age": a, "time": round(self.tyre_time(c, a) + mid_fuel, 3)}
                    for a in range(1, self.max_stint(c) + 1)] for c in DRY_COMPOUNDS}

    def to_dict(self) -> dict:
        return {"compounds": {c: p.to_dict() for c, p in self.params.items()},
                "residual_sd": round(self.residual_sd, 3), "laps_used": self.n_laps,
                "fuel_per_lap": self.fuel}
