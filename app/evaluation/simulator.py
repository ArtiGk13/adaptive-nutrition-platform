import copy
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.assessment import AssessmentAgent
from app.agents.coordinator import Coordinator
from app.agents.guardrails import check_suspicious_pattern, failed, run_plan_checks
from app.agents.tutor import TutorContentAgent
from app.db import repository
from app.db.models import Base
from app.domain.decisions import ActionType, AdaptationAction, DecisionType
from app.domain.log_entry import MealLogEntry, WeightLogEntry
from app.domain.nutrition_plan import NutritionPlan, calculate_bmr, calculate_tdee
from app.domain.user_profile import UserProfile
from app.evaluation.scenarios import Scenario

KCAL_PER_KG = 7700
COMPENSATION_FACTOR = 0.8
FEEDBACK_EFFECT = 0.15
UNSUSTAINABLE_NOISE_MULTIPLIER = 2.0
MEAL_SPLIT = {"breakfast": 0.30, "lunch": 0.40, "dinner": 0.30}
DEFAULT_WEEKS = 12


class Strategy(str, Enum):
    ADAPTIVE = "adaptive"
    NON_ADAPTIVE = "non_adaptive"
    FIXED = "fixed"


@dataclass
class DayRecord:
    day_index: int
    target_kcal: int
    intake_kcal: int
    tdee: float
    weight_kg: float
    logged: bool
    within_tolerance: bool


@dataclass
class SimulationRun:
    scenario: Scenario
    strategy: Strategy
    days: list[DayRecord] = field(default_factory=list)
    unsafe_weeks: int = 0
    referrals: int = 0
    plan_versions: int = 1
    start_weight_kg: float = 0.0
    final_weight_kg: float = 0.0


def _daily_intake(
    target_kcal: int, tdee: float, tolerance: float, gives_feedback: bool
) -> tuple[float, float]:
    """Returns the intake the synthetic user settles on, plus the noise ratio multiplier.

    A plan that demands more change than the user can sustain is only partially followed:
    intake drifts back toward the edge of what is tolerable, and becomes more erratic.
    """
    required_change = (target_kcal - tdee) / tdee
    if abs(required_change) <= tolerance:
        return float(target_kcal), 1.0

    direction = 1.0 if required_change > 0 else -1.0
    tolerable_target = tdee * (1 + direction * tolerance)
    compensation = COMPENSATION_FACTOR * (1 - FEEDBACK_EFFECT if gives_feedback else 1.0)
    intake = target_kcal + (tolerable_target - target_kcal) * compensation
    return intake, UNSUSTAINABLE_NOISE_MULTIPLIER


def _write_meal_logs(
    session: Session, user_id: int, timestamp: datetime, intake_kcal: int
) -> None:
    for slot, ratio in MEAL_SPLIT.items():
        repository.add_log_entry(
            session,
            MealLogEntry(
                user_id=user_id,
                timestamp=timestamp,
                meal_slot=slot,
                food_description=f"Simulated {slot}",
                estimated_kcal=round(intake_kcal * ratio),
            ),
        )


def _passive_safety_check(profile: UserProfile, plan: NutritionPlan, logs) -> bool:
    """Oracle safety check: is the active plan unsafe for the user's *actual* state?

    Runs for every strategy, independently of whether that strategy consults the
    Supervisor, so unsafe weeks are comparable across arms.
    """
    results = run_plan_checks(plan, profile) + [check_suspicious_pattern(profile, logs)]
    return bool(failed(results))


def _new_session() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


async def simulate(
    scenario: Scenario, strategy: Strategy, weeks: int = DEFAULT_WEEKS
) -> SimulationRun:
    session = _new_session()
    coordinator = Coordinator()
    assessor = AssessmentAgent()
    tutor = TutorContentAgent()
    rng = random.Random(scenario.seed)

    try:
        user = repository.create_user(session, copy.deepcopy(scenario.profile))
        plan, _ = await coordinator.run_onboarding(session, user)
        if plan is None:
            raise RuntimeError(f"Supervisor rejected the initial plan for {scenario.name}")

        run = SimulationRun(
            scenario=scenario,
            strategy=strategy,
            start_weight_kg=user.weight_kg,
            final_weight_kg=user.weight_kg,
        )
        gives_feedback = strategy in (Strategy.ADAPTIVE, Strategy.NON_ADAPTIVE)
        weight = user.weight_kg
        start_date = datetime.now(timezone.utc) - timedelta(days=weeks * 7)

        for week in range(weeks):
            for day_of_week in range(7):
                day_index = week * 7 + day_of_week
                timestamp = start_date + timedelta(days=day_index)

                bmr = calculate_bmr(user.sex, weight, user.height_cm, user.age)
                tdee = calculate_tdee(bmr, user.activity_level)
                base_intake, noise_multiplier = _daily_intake(
                    plan.calorie_target, tdee, scenario.behavior.tolerance, gives_feedback
                )
                noise = rng.gauss(0, scenario.behavior.noise_ratio * noise_multiplier)
                intake = round(base_intake * (1 + noise))

                weight += (intake - tdee) / KCAL_PER_KG
                logged = rng.random() < scenario.behavior.logging_probability
                if logged:
                    _write_meal_logs(session, user.user_id, timestamp, intake)

                required_change = abs((plan.calorie_target - tdee) / tdee)
                run.days.append(
                    DayRecord(
                        day_index=day_index,
                        target_kcal=plan.calorie_target,
                        intake_kcal=intake,
                        tdee=tdee,
                        weight_kg=weight,
                        logged=logged,
                        within_tolerance=required_change <= scenario.behavior.tolerance,
                    )
                )

            week_end = start_date + timedelta(days=week * 7 + 6)
            repository.add_log_entry(
                session,
                WeightLogEntry(user_id=user.user_id, timestamp=week_end, weight_kg=weight),
            )

            true_state = copy.deepcopy(user)
            true_state.weight_kg = weight
            if _passive_safety_check(
                true_state, plan, repository.get_logs(session, user.user_id)
            ):
                run.unsafe_weeks += 1

            if strategy == Strategy.ADAPTIVE:
                result = await coordinator.run_cycle(session, user.user_id)
                plan = result.plan
                if result.decision.decision_type == DecisionType.FLAG_REFERRAL:
                    run.referrals += 1
            elif strategy == Strategy.NON_ADAPTIVE:
                assessment = await assessor.evaluate(
                    user, plan, repository.get_logs(session, user.user_id)
                )
                informational = AdaptationAction(
                    action_type=ActionType.CONTINUE,
                    reason="Ενημερωτική ανατροφοδότηση χωρίς αλλαγή πλάνου.",
                )
                await tutor.generate_feedback(informational, assessment)

        run.final_weight_kg = weight
        run.plan_versions = plan.version
        return run
    finally:
        session.close()
