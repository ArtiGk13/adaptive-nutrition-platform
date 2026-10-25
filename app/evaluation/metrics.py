import statistics
from dataclasses import asdict, dataclass

from app.domain.user_profile import GoalType
from app.evaluation.simulator import SimulationRun, Strategy

MAINTENANCE_BAND_KG = 1.0
UNSAFE_WEEK_PENALTY = 0.05

EFFECTIVENESS_WEIGHTS = {
    "goal_progress": 0.35,
    "mean_adherence": 0.25,
    "consistency": 0.20,
    "suitability": 0.20,
}


@dataclass
class RunMetrics:
    scenario: str
    strategy: str
    mean_adherence: float
    consistency: float
    suitability: float
    logging_ratio: float
    weight_change_kg: float
    goal_progress: float
    goal_completed: bool
    unsafe_weeks: int
    referrals: int
    plan_versions: int
    overall_effectiveness: float
    refused_at_onboarding: bool = False
    refusal_reason: str = ""

    def as_row(self) -> dict:
        return asdict(self)


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _goal_progress(run: SimulationRun) -> float:
    achieved = run.final_weight_kg - run.start_weight_kg
    needed = run.scenario.goal_weight_kg - run.start_weight_kg

    if run.scenario.profile.goal_type == GoalType.MAINTENANCE:
        return _clip(1 - abs(achieved) / MAINTENANCE_BAND_KG)
    return _clip(achieved / needed)


def compute_metrics(run: SimulationRun) -> RunMetrics:
    if run.refused_at_onboarding:
        # Nothing was planned, so there is nothing to score. Reporting zeros here would be
        # read as poor performance rather than as a refusal, so the flag carries the meaning.
        return RunMetrics(
            scenario=run.scenario.name,
            strategy=run.strategy.value,
            mean_adherence=0.0,
            consistency=0.0,
            suitability=0.0,
            logging_ratio=0.0,
            weight_change_kg=0.0,
            goal_progress=0.0,
            goal_completed=False,
            unsafe_weeks=0,
            referrals=1,
            plan_versions=0,
            overall_effectiveness=0.0,
            refused_at_onboarding=True,
            refusal_reason=run.refusal_reason,
        )

    daily_adherence = [
        _clip(1 - abs(day.intake_kcal - day.target_kcal) / day.target_kcal)
        for day in run.days
    ]
    mean_adherence = statistics.fmean(daily_adherence)
    consistency = _clip(1 - statistics.pstdev(daily_adherence) * 2)
    suitability = statistics.fmean([1.0 if day.within_tolerance else 0.0 for day in run.days])
    logging_ratio = statistics.fmean([1.0 if day.logged else 0.0 for day in run.days])
    goal_progress = _goal_progress(run)

    weighted = (
        EFFECTIVENESS_WEIGHTS["goal_progress"] * goal_progress
        + EFFECTIVENESS_WEIGHTS["mean_adherence"] * mean_adherence
        + EFFECTIVENESS_WEIGHTS["consistency"] * consistency
        + EFFECTIVENESS_WEIGHTS["suitability"] * suitability
    )
    penalty = UNSAFE_WEEK_PENALTY * run.unsafe_weeks

    return RunMetrics(
        scenario=run.scenario.name,
        strategy=run.strategy.value,
        mean_adherence=round(mean_adherence, 3),
        consistency=round(consistency, 3),
        suitability=round(suitability, 3),
        logging_ratio=round(logging_ratio, 3),
        weight_change_kg=round(run.final_weight_kg - run.start_weight_kg, 2),
        goal_progress=round(goal_progress, 3),
        goal_completed=goal_progress >= 0.99,
        unsafe_weeks=run.unsafe_weeks,
        referrals=run.referrals,
        plan_versions=run.plan_versions,
        overall_effectiveness=round(_clip(weighted - penalty), 3),
    )


def summarise_by_strategy(results: list[RunMetrics]) -> dict[str, dict[str, float]]:
    """Averages exclude scenarios the Supervisor refused, which produced no run to measure."""
    summary: dict[str, dict[str, float]] = {}
    for strategy in Strategy:
        rows = [
            row
            for row in results
            if row.strategy == strategy.value and not row.refused_at_onboarding
        ]
        if not rows:
            continue
        summary[strategy.value] = {
            "mean_adherence": round(statistics.fmean(r.mean_adherence for r in rows), 3),
            "consistency": round(statistics.fmean(r.consistency for r in rows), 3),
            "suitability": round(statistics.fmean(r.suitability for r in rows), 3),
            "goal_progress": round(statistics.fmean(r.goal_progress for r in rows), 3),
            "goals_completed": sum(1 for r in rows if r.goal_completed),
            "unsafe_weeks": sum(r.unsafe_weeks for r in rows),
            "referrals": sum(r.referrals for r in rows),
            "overall_effectiveness": round(
                statistics.fmean(r.overall_effectiveness for r in rows), 3
            ),
        }
    return summary
