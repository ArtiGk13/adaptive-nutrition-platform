from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AssessmentResultORM,
    LogEntryORM,
    NutritionPlanORM,
    SupervisorDecisionORM,
    UserProfileORM,
)
from app.domain.assessment import AssessmentFlag, AssessmentResult
from app.domain.decisions import DecisionType, SupervisorDecision
from app.domain.log_entry import (
    ActivityLogEntry,
    LogEntry,
    LogType,
    MealLogEntry,
    WeightLogEntry,
)
from app.domain.nutrition_plan import (
    MacroTargets,
    MealSlot,
    NutritionPlan,
    PlanStatus,
)
from app.domain.user_profile import ActivityLevel, GoalType, Role, Sex, UserProfile


class SupervisorApprovalRequired(Exception):
    """Raised when a plan is persisted without an approving Supervisor decision."""


def _profile_to_domain(row: UserProfileORM) -> UserProfile:
    return UserProfile(
        user_id=row.user_id,
        name=row.name,
        age=row.age,
        sex=Sex(row.sex),
        height_cm=row.height_cm,
        weight_kg=row.weight_kg,
        activity_level=ActivityLevel(row.activity_level),
        goal_type=GoalType(row.goal_type),
        role=Role(row.role),
        adherence_level=row.adherence_level,
        difficulties=list(row.difficulties or []),
        current_plan_id=row.current_plan_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _plan_to_domain(row: NutritionPlanORM) -> NutritionPlan:
    return NutritionPlan(
        plan_id=row.plan_id,
        user_id=row.user_id,
        version=row.version,
        calorie_target=row.calorie_target,
        macro_targets=MacroTargets(**row.macro_targets),
        meal_structure=[MealSlot(**slot) for slot in row.meal_structure],
        status=PlanStatus(row.status),
        rationale=row.rationale,
        created_at=row.created_at,
        sustainable_target_kcal=row.sustainable_target_kcal,
        target_weight_kg=row.target_weight_kg,
    )


def _log_to_domain(row: LogEntryORM) -> LogEntry:
    if row.type == LogType.MEAL:
        return MealLogEntry(
            log_id=row.log_id,
            user_id=row.user_id,
            timestamp=row.timestamp,
            meal_slot=row.meal_slot,
            food_description=row.food_description,
            estimated_kcal=row.estimated_kcal,
            estimated_macros=dict(row.estimated_macros or {}),
        )
    if row.type == LogType.WEIGHT:
        return WeightLogEntry(
            log_id=row.log_id,
            user_id=row.user_id,
            timestamp=row.timestamp,
            weight_kg=row.weight_kg,
        )
    return ActivityLogEntry(
        log_id=row.log_id,
        user_id=row.user_id,
        timestamp=row.timestamp,
        activity_type=row.activity_type,
        duration_min=row.duration_min,
        estimated_kcal_burned=row.estimated_kcal_burned,
    )


def create_user(session: Session, profile: UserProfile) -> UserProfile:
    row = UserProfileORM(
        name=profile.name,
        age=profile.age,
        sex=profile.sex.value,
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        activity_level=profile.activity_level.value,
        goal_type=profile.goal_type.value,
        role=profile.role.value,
        adherence_level=profile.adherence_level,
        difficulties=list(profile.difficulties),
    )
    session.add(row)
    session.commit()
    return _profile_to_domain(row)


def get_user(session: Session, user_id: int) -> UserProfile | None:
    row = session.get(UserProfileORM, user_id)
    return _profile_to_domain(row) if row else None


def list_users(session: Session) -> list[UserProfile]:
    rows = session.scalars(select(UserProfileORM)).all()
    return [_profile_to_domain(row) for row in rows]


def update_user_adherence(
    session: Session, user_id: int, adherence_level: float, difficulties: list[str]
) -> None:
    row = session.get(UserProfileORM, user_id)
    if row is None:
        return
    row.adherence_level = adherence_level
    row.difficulties = difficulties
    session.commit()


def update_user_weight(session: Session, user_id: int, weight_kg: float) -> None:
    row = session.get(UserProfileORM, user_id)
    if row is None:
        return
    row.weight_kg = weight_kg
    session.commit()


def save_plan(
    session: Session, plan: NutritionPlan, decision: SupervisorDecision
) -> NutritionPlan:
    if not decision.approved:
        raise SupervisorApprovalRequired(
            f"Plan for user {plan.user_id} rejected by Supervisor: {decision.decision_type.value}"
        )

    previous = session.scalars(
        select(NutritionPlanORM)
        .where(NutritionPlanORM.user_id == plan.user_id)
        .where(NutritionPlanORM.status == PlanStatus.ACTIVE.value)
    ).all()
    for old in previous:
        old.status = PlanStatus.SUPERSEDED.value

    row = NutritionPlanORM(
        user_id=plan.user_id,
        version=_next_version(session, plan.user_id),
        calorie_target=plan.calorie_target,
        macro_targets=vars(plan.macro_targets),
        meal_structure=[vars(slot) for slot in plan.meal_structure],
        status=PlanStatus.ACTIVE.value,
        rationale=plan.rationale,
        sustainable_target_kcal=plan.sustainable_target_kcal,
        target_weight_kg=plan.target_weight_kg,
    )
    session.add(row)
    session.flush()

    user_row = session.get(UserProfileORM, plan.user_id)
    if user_row is not None:
        user_row.current_plan_id = row.plan_id

    session.commit()
    return _plan_to_domain(row)


def _next_version(session: Session, user_id: int) -> int:
    count = len(
        session.scalars(
            select(NutritionPlanORM).where(NutritionPlanORM.user_id == user_id)
        ).all()
    )
    return count + 1


def get_active_plan(session: Session, user_id: int) -> NutritionPlan | None:
    row = session.scalars(
        select(NutritionPlanORM)
        .where(NutritionPlanORM.user_id == user_id)
        .where(NutritionPlanORM.status == PlanStatus.ACTIVE.value)
        .order_by(NutritionPlanORM.plan_id.desc())
    ).first()
    return _plan_to_domain(row) if row else None


def get_plans(session: Session, user_id: int) -> list[NutritionPlan]:
    rows = session.scalars(
        select(NutritionPlanORM)
        .where(NutritionPlanORM.user_id == user_id)
        .order_by(NutritionPlanORM.version)
    ).all()
    return [_plan_to_domain(row) for row in rows]


def add_log_entry(session: Session, entry: LogEntry) -> LogEntry:
    row = LogEntryORM(user_id=entry.user_id, timestamp=entry.timestamp, type=entry.type.value)
    if isinstance(entry, MealLogEntry):
        row.meal_slot = entry.meal_slot
        row.food_description = entry.food_description
        row.estimated_kcal = entry.estimated_kcal
        row.estimated_macros = dict(entry.estimated_macros)
    elif isinstance(entry, WeightLogEntry):
        row.weight_kg = entry.weight_kg
    else:
        row.activity_type = entry.activity_type
        row.duration_min = entry.duration_min
        row.estimated_kcal_burned = entry.estimated_kcal_burned

    session.add(row)
    session.commit()
    return _log_to_domain(row)


def get_logs(session: Session, user_id: int) -> list[LogEntry]:
    rows = session.scalars(
        select(LogEntryORM)
        .where(LogEntryORM.user_id == user_id)
        .order_by(LogEntryORM.timestamp)
    ).all()
    return [_log_to_domain(row) for row in rows]


def save_assessment(session: Session, assessment: AssessmentResult) -> AssessmentResult:
    row = AssessmentResultORM(
        user_id=assessment.user_id,
        plan_id=assessment.plan_id,
        timestamp=assessment.timestamp,
        adherence_score=assessment.adherence_score,
        average_daily_kcal=assessment.average_daily_kcal,
        deviations=list(assessment.deviations),
        detected_difficulties=list(assessment.detected_difficulties),
        proposed_flag=assessment.proposed_flag.value,
    )
    session.add(row)
    session.commit()
    assessment.assessment_id = row.assessment_id
    return assessment


def get_assessments(session: Session, user_id: int) -> list[AssessmentResult]:
    rows = session.scalars(
        select(AssessmentResultORM)
        .where(AssessmentResultORM.user_id == user_id)
        .order_by(AssessmentResultORM.timestamp)
    ).all()
    return [
        AssessmentResult(
            assessment_id=row.assessment_id,
            user_id=row.user_id,
            plan_id=row.plan_id,
            timestamp=row.timestamp,
            adherence_score=row.adherence_score,
            average_daily_kcal=row.average_daily_kcal,
            deviations=list(row.deviations or []),
            detected_difficulties=list(row.detected_difficulties or []),
            proposed_flag=AssessmentFlag(row.proposed_flag),
        )
        for row in rows
    ]


def save_decision(session: Session, decision: SupervisorDecision) -> SupervisorDecision:
    row = SupervisorDecisionORM(
        user_id=decision.user_id,
        cycle_timestamp=decision.cycle_timestamp,
        decision_type=decision.decision_type.value,
        guardrail_checks_passed=decision.guardrail_checks_passed,
        failed_checks=list(decision.failed_checks),
        notes=decision.notes,
        resulting_plan_version=decision.resulting_plan_version,
    )
    session.add(row)
    session.commit()
    decision.decision_id = row.decision_id
    return decision


def get_decisions(session: Session, user_id: int) -> list[SupervisorDecision]:
    rows = session.scalars(
        select(SupervisorDecisionORM)
        .where(SupervisorDecisionORM.user_id == user_id)
        .order_by(SupervisorDecisionORM.cycle_timestamp)
    ).all()
    return [
        SupervisorDecision(
            decision_id=row.decision_id,
            user_id=row.user_id,
            cycle_timestamp=row.cycle_timestamp,
            decision_type=DecisionType(row.decision_type),
            guardrail_checks_passed=row.guardrail_checks_passed,
            failed_checks=list(row.failed_checks or []),
            notes=row.notes,
            resulting_plan_version=row.resulting_plan_version,
        )
        for row in rows
    ]


def load_state(
    session: Session, user_id: int
) -> tuple[UserProfile | None, NutritionPlan | None, list[LogEntry]]:
    profile = get_user(session, user_id)
    if profile is None:
        return None, None, []
    return profile, get_active_plan(session, user_id), get_logs(session, user_id)
