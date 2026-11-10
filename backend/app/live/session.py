"""A live strategy session: replays a real race lap by lap while the AI runs its own car.

Each tick:
  1. refit the tyre model and pit-loss estimate using only laps seen so far (no hindsight)
  2. advance the shadow car one lap
  3. let the pit wall assess the new situation and schedule the next stop
  4. publish one frame to every connected dashboard over WebSocket
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Callable, Optional

from ..data.schemas import NEUTRALISED, RaceData
from ..engine import engineer
from ..engine.degradation import TyreModel
from ..engine.pitloss import estimate_pit_loss
from ..engine.pitwall import Assessment, Call, PitWall
from ..engine.shadow import ShadowRace
from .state import leaderboard


class RaceSession:
    def __init__(self, race: RaceData, driver: str, mode: str = "auto",
                 fixed_stops: Optional[list[tuple[int, str]]] = None, branch_lap: int = 1,
                 seconds_per_lap: float = 2.0, on_finish: Optional[Callable[["RaceSession"], None]] = None):
        if driver not in race.index():
            raise ValueError(f"No laps for driver {driver}")
        self.id = uuid.uuid4().hex[:12]
        self.race = race
        self.driver = driver
        self.mode = mode
        self.fixed_stops = sorted(fixed_stops or [])
        self.branch_lap = max(1, branch_lap)
        self.interval = seconds_per_lap
        self.on_finish = on_finish

        self.shadow = ShadowRace(race, driver, self.branch_lap)
        self.pitwall = PitWall(race, driver)
        self.lap = 0
        self.paused = False
        self.finished = False
        self.model: Optional[TyreModel] = None
        self.pit_loss = 22.0
        self.assessment: Optional[Assessment] = None
        self.board: list[dict] = []
        self.frames: list[dict] = []
        self.subscribers: set[asyncio.Queue] = set()
        self._task: Optional[asyncio.Task] = None
        self.summary: Optional[dict] = None
        self._dnf_announced = False

    # ---- pub/sub -------------------------------------------------------
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self.subscribers.discard(q)

    async def publish(self, msg: dict) -> None:
        for q in list(self.subscribers):
            await q.put(msg)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        try:
            while not self.finished:
                if self.paused:
                    await asyncio.sleep(0.2)
                    continue
                await self.publish(self.advance())
                if self.finished:
                    await self.publish({"type": "finished", "summary": self.summary})
                    break
                await asyncio.sleep(self.interval)
        except asyncio.CancelledError:
            pass

    async def jump_to(self, lap: int) -> None:
        while self.lap < min(lap, self.race.total_laps) and not self.finished:
            await self.publish(self.advance())
        if self.finished:
            await self.publish({"type": "finished", "summary": self.summary})

    def stop(self) -> None:
        if self._task:
            self._task.cancel()

    # ---- the tick ------------------------------------------------------
    def advance(self) -> dict:
        n = self.lap + 1
        race = self.race
        prev_status = race.track_status(n - 1) if n > 1 else "GREEN"
        self.model = TyreModel.fit(race, up_to_lap=n)
        self.pit_loss = estimate_pit_loss(race, up_to_lap=n)

        if self.mode == "fixed":
            for k, c in self.fixed_stops:
                if k == n and n > self.branch_lap:
                    self.shadow.schedule_pit(k, c)

        step = self.shadow.step(n, self.model, self.pit_loss)
        self.lap = n
        self.board = leaderboard(race, n)
        status = race.track_status(n)
        calls: list[Call] = []

        # race-control style events
        if status != prev_status:
            if status in NEUTRALISED or status == "YELLOW":
                text = {"SC": "SAFETY CAR deployed.", "VSC": "VIRTUAL SAFETY CAR deployed.",
                        "RED": "RED FLAG.", "YELLOW": "Yellow flags."}[status]
                calls.append(Call(n, "RACE", "high" if status in NEUTRALISED else "low", text))
            elif prev_status in NEUTRALISED:
                calls.append(Call(n, "RACE", "medium", "Track clear. Green flag."))
        real = self.shadow.laps.get(n)
        if real and real.pit_out:
            calls.append(Call(n, "INFO", "low", f"Real {self.driver} pitted on lap {n - 1}, "
                                               f"out on {real.compound.title()}s."))

        if step is None:
            self.assessment = None
            if self.shadow.car.retired and not self._dnf_announced:
                self._dnf_announced = True
                calls.append(Call(n, "INFO", "high", f"Real {self.driver} is out of the race; shadow car stops too."))
        elif n >= self.branch_lap and n < race.total_laps:
            fixed_next = None
            if self.mode == "fixed":
                fixed_next = next(((k, c) for k, c in self.fixed_stops if k > n), None)
            self.assessment = self.pitwall.assess(n, self.shadow.car, self.model, self.pit_loss, fixed_next)
            calls.extend(self.assessment.calls)
            if self.mode == "auto" and self.assessment.box_now:
                self.shadow.schedule_pit(*self.assessment.box_now)
        if n == self.branch_lap and self.branch_lap > 1:
            calls.insert(0, Call(n, "INFO", "medium", f"AI takes over {self.driver}'s strategy from here."))

        frame = self._frame(n, status, calls)
        self.frames.append(frame)
        if n >= race.total_laps:
            self._finish()
        return frame

    def _frame(self, n: int, status: str, calls: list[Call]) -> dict:
        real = self.shadow.laps.get(n)
        me = next((r for r in self.board if r["driver"] == self.driver), None)
        delta = self.shadow.delta(n)
        return {
            "type": "lap",
            "lap": n,
            "total_laps": self.race.total_laps,
            "track_status": status,
            "leaderboard": self.board,
            "focus": {
                "driver": self.driver,
                "real": {
                    "position": me["position"] if me else None,
                    "compound": real.compound if real else None,
                    "age": real.tyre_life if real else None,
                    "lap_time": round(real.lap_time, 3) if real and real.lap_time else None,
                    "race_time": round(real.race_time, 3) if real and real.race_time else None,
                    "stops": [s for s in self.shadow.actual_stops() if s["lap"] < n],
                },
                "shadow": {
                    **self.shadow.car.to_dict(),
                    "position": self.shadow.virtual_position(n),
                    "delta": round(delta, 3) if delta is not None else None,
                    "active": n > self.branch_lap,
                },
            },
            "calls": [c.to_dict() for c in calls],
            "plans": [p.to_dict() for p in self.assessment.plans[:3]] if self.assessment else [],
            "undercut": self.assessment.undercut if self.assessment else None,
            "model": {**self.model.to_dict(), "curves": self.model.curves(), "pit_loss": round(self.pit_loss, 2)},
        }

    def _finish(self) -> None:
        self.finished = True
        last = max((f for f in self.frames if f["focus"]["shadow"]["delta"] is not None),
                   key=lambda f: f["lap"], default=None)
        self.summary = {
            "driver": self.driver,
            "mode": self.mode,
            "branch_lap": self.branch_lap,
            "final_delta": last["focus"]["shadow"]["delta"] if last else None,
            "shadow_position": last["focus"]["shadow"]["position"] if last else None,
            "actual_position": last["focus"]["real"]["position"] if last else None,
            "shadow_stops": [{"lap": k, "compound": c} for k, c in self.shadow.car.pits],
            "actual_stops": self.shadow.actual_stops(),
            "retired": self.shadow.car.retired,
            "last_lap": last["lap"] if last else None,
        }
        if self.on_finish:
            try:
                self.on_finish(self)
            except Exception:
                pass

    # ---- engineer ------------------------------------------------------
    async def ask(self, question: str) -> dict:
        if self.model is None:
            return {"answer": "Lights haven't gone out yet. Start the session and ask again.", "source": "rules"}
        return await engineer.answer(question, self)

    def state_summary(self) -> dict:
        frame = self.frames[-1] if self.frames else {}
        return {k: frame.get(k) for k in ("lap", "total_laps", "track_status", "focus", "plans", "undercut")} | {
            "leaderboard": [{k: r[k] for k in ("position", "driver", "gap", "compound", "tyre_age", "stops")}
                            for r in self.board],
            "pit_loss": self.pit_loss,
        }

    def init_payload(self) -> dict:
        return {"type": "init", "session": self.info(), "race": self.race.summary(), "frames": self.frames,
                "summary": self.summary}

    def info(self) -> dict:
        return {"id": self.id, "driver": self.driver, "mode": self.mode, "branch_lap": self.branch_lap,
                "fixed_stops": [{"lap": k, "compound": c} for k, c in self.fixed_stops],
                "seconds_per_lap": self.interval, "lap": self.lap, "paused": self.paused,
                "finished": self.finished, "race_id": self.race.race_id}
