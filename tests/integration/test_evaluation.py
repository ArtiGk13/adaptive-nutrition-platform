import pytest

from app.evaluation.metrics import compute_metrics, summarise_by_strategy
from app.evaluation.runner import run_all, write_csv
from app.evaluation.scenarios import SCENARIOS
from app.evaluation.simulator import Strategy, simulate

WEEKS = 4
LOW_TOLERANCE = next(s for s in SCENARIOS if s.name == "weight_loss_low_tolerance")
CONSISTENT = next(s for s in SCENARIOS if s.name == "weight_loss_consistent")


async def test_simulation_is_deterministic():
    first = compute_metrics(await simulate(CONSISTENT, Strategy.FIXED, weeks=WEEKS))
    second = compute_metrics(await simulate(CONSISTENT, Strategy.FIXED, weeks=WEEKS))
    assert first == second


async def test_all_strategies_see_identical_user_randomness():
    """Paired comparison: arms may only differ because of the system, not the dice."""
    adaptive = await simulate(CONSISTENT, Strategy.ADAPTIVE, weeks=2)
    fixed = await simulate(CONSISTENT, Strategy.FIXED, weeks=2)
    assert [day.target_kcal for day in adaptive.days[:7]] == [
        day.target_kcal for day in fixed.days[:7]
    ]


async def test_fixed_plan_never_changes():
    run = await simulate(LOW_TOLERANCE, Strategy.FIXED, weeks=WEEKS)
    assert run.plan_versions == 1
    assert len({day.target_kcal for day in run.days}) == 1


async def test_adaptive_plan_adjusts_for_unsustainable_target():
    run = await simulate(LOW_TOLERANCE, Strategy.ADAPTIVE, weeks=WEEKS)
    assert run.plan_versions > 1
    assert len({day.target_kcal for day in run.days}) > 1


async def test_adaptive_beats_fixed_on_suitability_for_low_tolerance_user():
    adaptive = compute_metrics(await simulate(LOW_TOLERANCE, Strategy.ADAPTIVE, weeks=8))
    fixed = compute_metrics(await simulate(LOW_TOLERANCE, Strategy.FIXED, weeks=8))
    assert adaptive.suitability > fixed.suitability
    assert adaptive.mean_adherence > fixed.mean_adherence


async def test_metrics_stay_within_bounds():
    run = await simulate(CONSISTENT, Strategy.ADAPTIVE, weeks=WEEKS)
    metrics = compute_metrics(run)
    for value in (
        metrics.mean_adherence,
        metrics.consistency,
        metrics.suitability,
        metrics.goal_progress,
        metrics.overall_effectiveness,
    ):
        assert 0.0 <= value <= 1.0


async def test_runner_produces_csv(tmp_path):
    results = await run_all(scenarios=[CONSISTENT], weeks=2)
    assert len(results) == len(Strategy)

    summary = summarise_by_strategy(results)
    assert set(summary) == {strategy.value for strategy in Strategy}

    path = write_csv(results, tmp_path / "results.csv")
    assert path.exists()
    assert "scenario,strategy" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
async def test_every_scenario_starts_with_an_approved_plan(scenario):
    run = await simulate(scenario, Strategy.FIXED, weeks=1)
    assert run.days
    assert run.days[0].target_kcal > 0
