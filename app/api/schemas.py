from datetime import datetime

from pydantic import BaseModel, Field

from app.agents.coordinator import CycleResult
from app.domain.assessment import AssessmentFlag, AssessmentResult
from app.domain.decisions import ActionType, AdaptationAction, DecisionType, SupervisorDecision
from app.domain.log_entry import ActivityLogEntry, LogEntry, MealLogEntry, WeightLogEntry
from app.domain.nutrition_plan import NutritionPlan
from app.domain.user_profile import ActivityLevel, GoalType, Role, Sex, UserProfile
from app.services.nutritionist_service import UserHistory, UserOverview


class MedicalHistory(BaseModel):
    """The minimum history a dietitian identified as required before issuing a plan."""

    allergies: list[str] = []
    intolerances: list[str] = []
    medical_conditions: list[str] = []
    family_history: list[str] = []
    medications: list[str] = []
    food_dislikes: list[str] = []


class ScreeningAnswers(BaseModel):
    """Signals that may only trigger a referral; they never influence a plan."""

    recent_weight_fluctuation: bool = False
    difficult_relationship_with_food: bool = False
    perceives_self_as_overweight: bool = False
    previous_diet_attempts: int = 0


class UserCreate(BaseModel):
    """Bounds here are sanity, not clinical judgement.

    Nothing validated the incoming numbers, so a profile could be stored with a negative
    height or an age of zero. The guardrails then refused to plan for it, which reads
    like a safety net but is not one: they examine what a plan would demand of a person,
    not whether the person was described coherently, and they do not see log entries at
    all. The limits below are the ones outside which a figure cannot describe an adult
    human being; the clinical range is the dietitian's and lives in the guardrails.
    """

    name: str = Field(min_length=1, max_length=120)
    age: int = Field(ge=1, le=120)
    sex: Sex
    height_cm: float = Field(gt=0, le=300)
    weight_kg: float = Field(gt=0, le=500)
    activity_level: ActivityLevel
    goal_type: GoalType
    role: Role = Role.USER
    history: MedicalHistory = MedicalHistory()
    screening: ScreeningAnswers = ScreeningAnswers()

    def to_domain(self) -> UserProfile:
        return UserProfile(
            name=self.name,
            age=self.age,
            sex=self.sex,
            height_cm=self.height_cm,
            weight_kg=self.weight_kg,
            activity_level=self.activity_level,
            goal_type=self.goal_type,
            role=self.role,
            **self.history.model_dump(),
            **self.screening.model_dump(),
        )


class UserRead(BaseModel):
    user_id: int
    name: str
    age: int
    sex: Sex
    height_cm: float
    weight_kg: float
    activity_level: ActivityLevel
    goal_type: GoalType
    role: Role
    adherence_level: float
    difficulties: list[str]
    current_plan_id: int | None
    history: MedicalHistory
    screening: ScreeningAnswers

    @classmethod
    def from_domain(cls, profile: UserProfile) -> "UserRead":
        return cls(
            user_id=profile.user_id,
            name=profile.name,
            age=profile.age,
            sex=profile.sex,
            height_cm=profile.height_cm,
            weight_kg=profile.weight_kg,
            activity_level=profile.activity_level,
            goal_type=profile.goal_type,
            role=profile.role,
            adherence_level=profile.adherence_level,
            difficulties=profile.difficulties,
            current_plan_id=profile.current_plan_id,
            history=MedicalHistory(
                allergies=profile.allergies,
                intolerances=profile.intolerances,
                medical_conditions=profile.medical_conditions,
                family_history=profile.family_history,
                medications=profile.medications,
                food_dislikes=profile.food_dislikes,
            ),
            screening=ScreeningAnswers(
                recent_weight_fluctuation=profile.recent_weight_fluctuation,
                difficult_relationship_with_food=profile.difficult_relationship_with_food,
                perceives_self_as_overweight=profile.perceives_self_as_overweight,
                previous_diet_attempts=profile.previous_diet_attempts,
            ),
        )


class MacroTargetsRead(BaseModel):
    protein_g: int
    carbs_g: int
    fat_g: int


class MealSlotRead(BaseModel):
    slot_name: str
    target_kcal: int


class PlanRead(BaseModel):
    plan_id: int | None
    user_id: int
    version: int
    calorie_target: int
    target_weight_kg: float | None
    macro_targets: MacroTargetsRead
    meal_structure: list[MealSlotRead]
    status: str
    rationale: str

    @classmethod
    def from_domain(cls, plan: NutritionPlan) -> "PlanRead":
        return cls(
            plan_id=plan.plan_id,
            user_id=plan.user_id,
            version=plan.version,
            calorie_target=plan.calorie_target,
            target_weight_kg=plan.target_weight_kg,
            macro_targets=MacroTargetsRead(**vars(plan.macro_targets)),
            meal_structure=[MealSlotRead(**vars(slot)) for slot in plan.meal_structure],
            status=plan.status.value,
            rationale=plan.rationale,
        )


class MealLogCreate(BaseModel):
    timestamp: datetime
    meal_slot: str = Field(min_length=1)
    food_description: str = Field(min_length=1, max_length=300)
    # A negative figure here is not refused anywhere downstream: it enters the daily
    # total, lowers the average, and the Assessment agent reports an adherence computed
    # from it as though it were a record of eating.
    estimated_kcal: int = Field(ge=0, le=20000)
    estimated_macros: dict[str, int] = {}

    def to_domain(self, user_id: int) -> MealLogEntry:
        return MealLogEntry(
            user_id=user_id,
            timestamp=self.timestamp,
            meal_slot=self.meal_slot,
            food_description=self.food_description,
            estimated_kcal=self.estimated_kcal,
            estimated_macros=self.estimated_macros,
        )


class WeightLogCreate(BaseModel):
    timestamp: datetime
    weight_kg: float = Field(gt=0, le=500)

    def to_domain(self, user_id: int) -> WeightLogEntry:
        return WeightLogEntry(user_id=user_id, timestamp=self.timestamp, weight_kg=self.weight_kg)


class ActivityLogCreate(BaseModel):
    timestamp: datetime
    activity_type: str = Field(min_length=1, max_length=120)
    duration_min: int = Field(ge=0, le=1440)
    estimated_kcal_burned: int = Field(ge=0, le=20000)

    def to_domain(self, user_id: int) -> ActivityLogEntry:
        return ActivityLogEntry(
            user_id=user_id,
            timestamp=self.timestamp,
            activity_type=self.activity_type,
            duration_min=self.duration_min,
            estimated_kcal_burned=self.estimated_kcal_burned,
        )


class LogRead(BaseModel):
    log_id: int | None
    user_id: int
    timestamp: datetime
    type: str
    details: dict

    @classmethod
    def from_domain(cls, entry: LogEntry) -> "LogRead":
        details = {
            key: value
            for key, value in vars(entry).items()
            if key not in {"log_id", "user_id", "timestamp", "type"}
        }
        return cls(
            log_id=entry.log_id,
            user_id=entry.user_id,
            timestamp=entry.timestamp,
            type=entry.type.value,
            details=details,
        )


class AssessmentRead(BaseModel):
    assessment_id: int | None
    plan_id: int
    adherence_score: float
    average_daily_kcal: float
    deviations: list[str]
    detected_difficulties: list[str]
    proposed_flag: AssessmentFlag

    @classmethod
    def from_domain(cls, assessment: AssessmentResult) -> "AssessmentRead":
        return cls(
            assessment_id=assessment.assessment_id,
            plan_id=assessment.plan_id,
            adherence_score=assessment.adherence_score,
            average_daily_kcal=assessment.average_daily_kcal,
            deviations=assessment.deviations,
            detected_difficulties=assessment.detected_difficulties,
            proposed_flag=assessment.proposed_flag,
        )


class ActionRead(BaseModel):
    action_type: ActionType
    reason: str

    @classmethod
    def from_domain(cls, action: AdaptationAction) -> "ActionRead":
        return cls(action_type=action.action_type, reason=action.reason)


class GuardrailCheckRead(BaseModel):
    code: str
    passed: bool
    message: str


class DecisionRead(BaseModel):
    decision_id: int | None
    decision_type: DecisionType
    approved: bool
    guardrail_checks_passed: bool
    failed_checks: list[str]
    notes: str
    # Recorded on the decision and simply not returned before; without it a trail of
    # decisions cannot be read in order. The version recorded beside it is not exposed:
    # a decision is built before the plan is stored, so the number it holds is the one
    # on the draft, not the one the stored plan ends up with.
    cycle_timestamp: datetime
    checks: list[GuardrailCheckRead]

    @classmethod
    def from_domain(cls, decision: SupervisorDecision) -> "DecisionRead":
        return cls(
            decision_id=decision.decision_id,
            decision_type=decision.decision_type,
            approved=decision.approved,
            guardrail_checks_passed=decision.guardrail_checks_passed,
            failed_checks=decision.failed_checks,
            notes=decision.notes,
            cycle_timestamp=decision.cycle_timestamp,
            checks=[
                GuardrailCheckRead(code=c.code, passed=c.passed, message=c.message)
                for c in decision.checks
            ],
        )


class UserOverviewRead(BaseModel):
    user_id: int
    name: str
    age: int
    sex: Sex
    goal_type: GoalType
    weight_kg: float
    adherence_level: float
    calorie_target: int | None
    target_weight_kg: float | None
    latest_flag: AssessmentFlag | None
    needs_referral: bool

    @classmethod
    def from_domain(cls, overview: UserOverview) -> "UserOverviewRead":
        profile = overview.profile
        return cls(
            user_id=profile.user_id,
            name=profile.name,
            age=profile.age,
            sex=profile.sex,
            goal_type=profile.goal_type,
            weight_kg=profile.weight_kg,
            adherence_level=profile.adherence_level,
            calorie_target=overview.active_plan.calorie_target if overview.active_plan else None,
            target_weight_kg=(
                overview.active_plan.target_weight_kg if overview.active_plan else None
            ),
            latest_flag=(
                overview.latest_assessment.proposed_flag if overview.latest_assessment else None
            ),
            needs_referral=overview.needs_referral,
        )


class UserHistoryRead(BaseModel):
    profile: UserRead
    plans: list[PlanRead]
    assessments: list[AssessmentRead]
    decisions: list[DecisionRead]

    @classmethod
    def from_domain(cls, history: UserHistory) -> "UserHistoryRead":
        return cls(
            profile=UserRead.from_domain(history.profile),
            plans=[PlanRead.from_domain(plan) for plan in history.plans],
            assessments=[
                AssessmentRead.from_domain(assessment) for assessment in history.assessments
            ],
            decisions=[DecisionRead.from_domain(decision) for decision in history.decisions],
        )


class PlanCreateResponse(BaseModel):
    plan: PlanRead | None
    supervisor_decision: DecisionRead


class CycleResponse(BaseModel):
    plan: PlanRead
    assessment: AssessmentRead
    action: ActionRead
    supervisor_decision: DecisionRead
    feedback_text: str | None
    support_text: str | None

    @classmethod
    def from_domain(cls, result: CycleResult) -> "CycleResponse":
        return cls(
            plan=PlanRead.from_domain(result.plan),
            assessment=AssessmentRead.from_domain(result.assessment),
            action=ActionRead.from_domain(result.action),
            supervisor_decision=DecisionRead.from_domain(result.decision),
            feedback_text=result.feedback_text,
            support_text=result.support_text,
        )
