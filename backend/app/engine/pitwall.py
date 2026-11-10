"""The pit wall: turns the optimizer's numbers into radio calls, lap by lap."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..data.schemas import DRY_COMPOUNDS, NEUTRALISED, RaceData
from .degradation import TyreModel
from .optimizer import Plan, best_plans
from .pitloss import effective_pit_loss
from .shadow import ShadowCar

OUTLAP_PENALTY = 1.2   # cold tyres on the out-lap, seconds
UNDERCUT_MARGIN = 0.3


@dataclass
class Call:
    lap: int
    kind: str          # BOX, SC_BOX, WINDOW, STAY_OUT, PLAN, UNDERCUT, THREAT, RACE, INFO
    priority: str      # high / medium / low
    message: str
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"lap": self.lap, "kind": self.kind, "priority": self.priority,
                "message": self.message, "data": self.data}


@dataclass
class Assessment:
    plans: list[Plan]
    calls: list[Call]
    box_now: tuple[int, str] | None = None
    rejoin: dict | None = None
    undercut: dict | None = None

    def to_dict(self) -> dict:
        return {"plans": [p.to_dict() for p in self.plans], "calls": [c.to_dict() for c in self.calls],
                "box_now": {"lap": self.box_now[0], "compound": self.box_now[1]} if self.box_now else None,
                "rejoin": self.rejoin, "undercut": self.undercut}


def undercut_gain(model: TyreModel, lap: int, rival: str, rival_comp: str, rival_age: int,
                  me: str, my_new: str, laps: int = 2) -> float:
    """Time won on fresh tyres while the rival stays out on old ones, minus the cold out-lap."""
    gain = 0.0
    for j in range(1, laps + 1):
        gain += model.lap_time(rival_comp, rival_age + j, lap + j, rival) - model.lap_time(my_new, j, lap + j, me)
    return gain - OUTLAP_PENALTY


class PitWall:
    def __init__(self, race: RaceData, driver: str):
        self.race = race
        self.driver = driver
        self.last_plan: str | None = None
        self._last_shape: tuple = ((), None)
        self._last: dict[str, int] = {}

    @staticmethod
    def _shape(plan: Plan) -> tuple:
        return tuple(c for _, c in plan.stops), plan.stops[0][0] if plan.stops else None

    def _plan_changed(self, plan: Plan, lap: int) -> bool:
        """A different tyre sequence, or the next stop moving by 3+ laps. Small drifts aren't news."""
        if self.last_plan is None:
            return False
        chain, first = self._shape(plan)
        old_chain, old_first = self._last_shape
        if old_first is not None and old_first <= lap + 1:  # we just made that stop
            return False
        if chain != old_chain:
            return True
        return first is not None and old_first is not None and abs(first - old_first) >= 3

    def _ready(self, key: str, lap: int, cooldown: int) -> bool:
        if lap - self._last.get(key, -999) < cooldown:
            return False
        self._last[key] = lap
        return True

    def field_at(self, lap: int) -> list[dict]:
        out = []
        for d, laps in self.race.index().items():
            if d == self.driver:
                continue
            l = laps.get(lap)
            if l and l.race_time is not None:
                out.append({"driver": d, "race_time": l.race_time, "compound": l.compound, "age": l.tyre_life})
        return sorted(out, key=lambda x: x["race_time"])

    def rejoin(self, lap: int, car: ShadowCar, loss: float) -> dict:
        field_ = self.field_at(lap)
        t = car.race_time + loss
        ahead = [f for f in field_ if f["race_time"] < t]
        behind = [f for f in field_ if f["race_time"] >= t]
        out = {"position": len(ahead) + 1}
        if ahead:
            out.update(ahead_of={"driver": ahead[-1]["driver"], "gap": round(t - ahead[-1]["race_time"], 1)})
        if behind:
            out.update(behind_of={"driver": behind[0]["driver"], "gap": round(behind[0]["race_time"] - t, 1)})
        return out

    def assess(self, lap: int, car: ShadowCar, model: TyreModel, pit_loss: float,
               fixed_next: tuple[int, str] | None = None) -> Assessment:
        status = self.race.track_status(lap)
        calls: list[Call] = []
        # if the car pitted this lap, plan from the fresh set it is about to fit
        compound, age, used = car.compound, car.age, set(car.used)
        if car.fit_next:
            compound, age = car.fit_next, 0
            used.add(car.fit_next)
        if car.pending:  # a stop is already scheduled; don't re-plan on top of it
            return Assessment([], calls)
        if compound not in DRY_COMPOUNDS:
            if self._ready("wet", lap, 10):
                calls.append(Call(lap, "INFO", "low", f"Running {compound.lower()}s. Dry-tyre model is paused."))
            return Assessment([], calls)

        cheap = effective_pit_loss(pit_loss, status) if status in NEUTRALISED else None
        plans = best_plans(model, self.driver, lap, compound, age, used, pit_loss, cheap)
        if not plans:
            return Assessment([], calls)
        best = plans[0]
        label = best.label()

        # fixed-strategy mode: we follow the human's plan, the AI comments
        if fixed_next is not None:
            target = fixed_next
            if target[0] == lap + 1:
                loss = effective_pit_loss(pit_loss, status)
                rj = self.rejoin(lap, car, loss)
                calls.append(Call(lap, "BOX", "high", f"Box box, as planned. {target[1].title()}s. "
                                  f"Rejoining P{rj['position']}.", {"rejoin": rj}))
                ai_first = best.next_stop
                if ai_first and ai_first[0] != lap + 1 and self._ready("disagree", lap, 5):
                    calls.append(Call(lap, "INFO", "medium", f"AI disagrees: its best plan is {label}."))
                return Assessment(plans, calls, box_now=target, rejoin=rj)
            if self._ready("fixed", lap, 8):
                calls.append(Call(lap, "STAY_OUT", "low", f"Following your plan: box lap {target[0]} for "
                                  f"{target[1].title()}s. AI's best right now: {label}."))
            return Assessment(plans, calls)

        box_now, rejoin_info = None, None
        nxt = best.next_stop
        if nxt and nxt[0] == lap + 1:
            loss = cheap if cheap is not None else pit_loss
            rejoin_info = self.rejoin(lap, car, loss)
            where = f" Rejoin P{rejoin_info['position']}"
            if "ahead_of" in rejoin_info:
                where += f", {rejoin_info['ahead_of']['gap']}s behind {rejoin_info['ahead_of']['driver']}"
            if status in NEUTRALISED:
                msg = (f"BOX BOX. {status} is out: stop costs about {loss:.0f}s instead of {pit_loss:.0f}s. "
                       f"{nxt[1].title()}s.{where}.")
                calls.append(Call(lap, "SC_BOX", "high", msg, {"rejoin": rejoin_info, "loss": loss}))
            else:
                calls.append(Call(lap, "BOX", "high", f"BOX BOX. {nxt[1].title()}s.{where}.",
                                  {"rejoin": rejoin_info, "plan": label}))
            box_now = nxt
        elif nxt and nxt[0] - lap <= 3:
            if self._ready("window", lap, 3):
                calls.append(Call(lap, "WINDOW", "medium",
                                  f"Pit window open. Target lap {nxt[0]} for {nxt[1].title()}s. Plan {label}."))
        elif self._ready("stay", lap, 6):
            gap2 = f" Next best is +{plans[1].delta:.1f}s." if len(plans) > 1 else ""
            calls.append(Call(lap, "STAY_OUT", "low",
                              f"Stay out. {compound.title()}s {'fresh' if age == 0 else f'at {age} laps'}, plan {label}.{gap2}"))

        changed = self._plan_changed(best, lap)
        if changed and not box_now and self._ready("plan", lap, 2):
            calls.append(Call(lap, "PLAN", "medium", f"Strategy update: now {label} (was {self.last_plan})."))
        if self.last_plan is None or changed or (self._last_shape[1] or 10**6) <= lap + 1:
            self.last_plan, self._last_shape = label, self._shape(best)

        undercut = None
        if status == "GREEN" and nxt and not box_now:
            undercut = self._undercut_checks(lap, car, model, nxt, calls)
        return Assessment(plans, calls, box_now=box_now, rejoin=rejoin_info, undercut=undercut)

    def _undercut_checks(self, lap: int, car: ShadowCar, model: TyreModel, nxt: tuple[int, str],
                         calls: list[Call]) -> dict | None:
        field_ = self.field_at(lap)
        ahead = [f for f in field_ if f["race_time"] < car.race_time]
        behind = [f for f in field_ if f["race_time"] > car.race_time]
        info = None
        if ahead and nxt[0] - lap <= 6:
            r = ahead[-1]
            gap = car.race_time - r["race_time"]
            gain = undercut_gain(model, lap, r["driver"], r["compound"], r["age"], self.driver, nxt[1])
            info = {"rival": r["driver"], "gap": round(gap, 2), "gain": round(gain, 2),
                    "on": gain > gap + UNDERCUT_MARGIN}
            if info["on"] and r["age"] >= 6 and self._ready(f"uc-{r['driver']}", lap, 4):
                calls.append(Call(lap, "UNDERCUT", "high",
                                  f"Undercut on {r['driver']} is ON: gap {gap:.1f}s, fresh tyres worth "
                                  f"~{gain:.1f}s over two laps. Consider boxing early.", info))
        if behind and car.age >= 8:
            r = behind[0]
            gap = r["race_time"] - car.race_time
            their_new = "HARD" if r["compound"] != "HARD" else "MEDIUM"
            gain = undercut_gain(model, lap, self.driver, car.compound, car.age, r["driver"], their_new)
            if r["age"] >= 8 and gain > gap + UNDERCUT_MARGIN and self._ready(f"th-{r['driver']}", lap, 5):
                calls.append(Call(lap, "THREAT", "medium",
                                  f"Undercut threat from {r['driver']}, {gap:.1f}s behind. If they box we lose "
                                  f"~{gain - gap:.1f}s. Cover?", {"rival": r["driver"], "gap": round(gap, 2),
                                                                 "gain": round(gain, 2)}))
        return info
