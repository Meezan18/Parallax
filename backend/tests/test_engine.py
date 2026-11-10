import asyncio

import pytest

from app.data.synthetic import TRUE_PIT_LOSS, TRUE_TYRES, generate_demo_race
from app.engine.degradation import TyreModel
from app.engine.optimizer import best_plans, evaluate_plan
from app.engine.pitloss import estimate_pit_loss
from app.live.session import RaceSession
from app.live.state import leaderboard


@pytest.fixture(scope="module")
def race():
    return generate_demo_race()


def test_tyre_model_recovers_true_degradation(race):
    model = TyreModel.fit(race)
    for c, (_, b, _) in TRUE_TYRES.items():
        assert model.params[c].b == pytest.approx(b, abs=0.015), c
    # pace ordering between compounds is preserved
    assert model.params["SOFT"].intercept < model.params["MEDIUM"].intercept < model.params["HARD"].intercept


def test_model_falls_back_to_priors_early(race):
    early = TyreModel.fit(race, up_to_lap=3)
    assert early.params["HARD"].n_laps < 8
    assert early.params["HARD"].b > 0


def test_pit_loss_estimate(race):
    assert estimate_pit_loss(race) == pytest.approx(TRUE_PIT_LOSS, abs=2.5)


def test_optimizer_respects_two_compound_rule(race):
    model = TyreModel.fit(race)
    plans = best_plans(model, "CAL", 1, "MEDIUM", 1, {"MEDIUM"}, 22.0)
    assert plans
    for p in plans:
        assert p.stops, "a dry race cannot be run on one compound"
        assert {c for _, c in p.stops} | {"MEDIUM"} != {"MEDIUM"}
    assert plans[0].delta == 0
    assert all(a.time <= b.time for a, b in zip(plans, plans[1:]))


def test_evaluate_plan_matches_optimizer(race):
    model = TyreModel.fit(race)
    best = best_plans(model, "CAL", 10, "MEDIUM", 10, {"MEDIUM"}, 22.0)[0]
    t = evaluate_plan(model, "CAL", 10, "MEDIUM", 10, best.stops, 22.0)
    assert t == pytest.approx(best.time, abs=1e-6)


def test_shadow_with_real_strategy_tracks_reality(race):
    """Re-running the driver's own strategy should land close to the real result."""
    probe = RaceSession(race, "CAL")
    actual = [(s["lap"], s["compound"]) for s in probe.shadow.actual_stops()]
    s = RaceSession(race, "CAL", mode="fixed", fixed_stops=actual)
    while not s.finished:
        s.advance()
    assert abs(s.summary["final_delta"]) < 4.0


def test_auto_session_runs_full_race(race):
    s = RaceSession(race, "ARN")
    while not s.finished:
        s.advance()
    assert len(s.frames) == race.total_laps
    assert s.summary["shadow_stops"], "the AI must stop at least once in a dry race"
    kinds = {c["kind"] for f in s.frames for c in f["calls"]}
    assert "RACE" in kinds and ({"BOX", "SC_BOX"} & kinds)


def test_leaderboard_handles_retirement(race):
    board = leaderboard(race, race.total_laps)
    assert board[0]["gap"] == "LEADER"
    assert any(r["retired"] for r in board)
    assert [r["position"] for r in board] == list(range(1, len(board) + 1))


def test_engineer_answers(race):
    s = RaceSession(race, "CAL")
    for _ in range(34):
        s.advance()

    def ask(q):
        return asyncio.run(s.ask(q))["answer"]

    assert "leads" in ask("who's leading?")
    assert "Safety Car" in ask("is there a safety car?") or "green" in ask("is there a safety car?").lower()
    assert "Plan" in ask("what's our plan?")
    assert "Shadow CAL" in ask("how is the ghost doing?")
    assert "P" in ask("where is DUV?")
    assert "to go" in ask("how many laps left")
