from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UserProfileORM(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    age: Mapped[int]
    sex: Mapped[str] = mapped_column(String(10))
    height_cm: Mapped[float]
    weight_kg: Mapped[float]
    activity_level: Mapped[str] = mapped_column(String(20))
    goal_type: Mapped[str] = mapped_column(String(20))
    role: Mapped[str] = mapped_column(String(20), default="user")
    adherence_level: Mapped[float] = mapped_column(default=0.0)
    difficulties: Mapped[list] = mapped_column(JSON, default=list)
    current_plan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    allergies: Mapped[list] = mapped_column(JSON, default=list)
    intolerances: Mapped[list] = mapped_column(JSON, default=list)
    medical_conditions: Mapped[list] = mapped_column(JSON, default=list)
    family_history: Mapped[list] = mapped_column(JSON, default=list)
    medications: Mapped[list] = mapped_column(JSON, default=list)
    food_dislikes: Mapped[list] = mapped_column(JSON, default=list)
    recent_weight_fluctuation: Mapped[bool] = mapped_column(Boolean, default=False)
    difficult_relationship_with_food: Mapped[bool] = mapped_column(Boolean, default=False)
    perceives_self_as_overweight: Mapped[bool] = mapped_column(Boolean, default=False)
    previous_diet_attempts: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class NutritionPlanORM(Base):
    __tablename__ = "nutrition_plans"

    plan_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.user_id"))
    version: Mapped[int] = mapped_column(default=1)
    calorie_target: Mapped[int]
    macro_targets: Mapped[dict] = mapped_column(JSON, default=dict)
    meal_structure: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="active")
    rationale: Mapped[str] = mapped_column(String(500), default="")
    sustainable_target_kcal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_weight_kg: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LogEntryORM(Base):
    __tablename__ = "log_entries"

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.user_id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    type: Mapped[str] = mapped_column(String(20))

    meal_slot: Mapped[str | None] = mapped_column(String(30), nullable=True)
    food_description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    estimated_kcal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_macros: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    weight_kg: Mapped[float | None] = mapped_column(nullable=True)

    activity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_kcal_burned: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AssessmentResultORM(Base):
    __tablename__ = "assessment_results"

    assessment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.user_id"))
    plan_id: Mapped[int] = mapped_column(ForeignKey("nutrition_plans.plan_id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    adherence_score: Mapped[float]
    average_daily_kcal: Mapped[float] = mapped_column(default=0.0)
    deviations: Mapped[list] = mapped_column(JSON, default=list)
    detected_difficulties: Mapped[list] = mapped_column(JSON, default=list)
    proposed_flag: Mapped[str] = mapped_column(String(30))


class SupervisorDecisionORM(Base):
    __tablename__ = "supervisor_decisions"

    decision_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.user_id"))
    cycle_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    decision_type: Mapped[str] = mapped_column(String(30))
    guardrail_checks_passed: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_checks: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(String(500), default="")
    resulting_plan_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
