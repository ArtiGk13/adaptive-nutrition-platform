from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.domain.nutrition_plan import NutritionPlan


class ActionType(str, Enum):
    CONTINUE = "continue"
    ADJUST_PLAN = "adjust_plan"
    EXTRA_SUPPORT = "extra_support"
    REFER_SPECIALIST = "refer_specialist"


class DecisionType(str, Enum):
    APPROVE_PLAN = "approve_plan"
    APPROVE_ADJUSTMENT = "approve_adjustment"
    HOLD = "hold"
    FLAG_REFERRAL = "flag_referral"


@dataclass
class AdaptationAction:
    action_type: ActionType
    reason: str
    new_plan: NutritionPlan | None = None

    @property
    def requires_change(self) -> bool:
        return self.new_plan is not None

    @property
    def needs_explanation(self) -> bool:
        return self.action_type != ActionType.CONTINUE


@dataclass(frozen=True)
class GuardrailCheck:
    """One limit the Supervisor tested, and what it found."""

    code: str
    passed: bool
    message: str


@dataclass
class SupervisorDecision:
    user_id: int
    cycle_timestamp: datetime
    decision_type: DecisionType
    guardrail_checks_passed: bool
    notes: str
    resulting_plan_version: int | None = None
    failed_checks: list[str] = field(default_factory=list)
    decision_id: int | None = None
    # Every check the Supervisor ran, each with what it concluded. Computed already and
    # thrown away before: only the failures were kept, which left a passing decision
    # able to say that limits were checked and not which ones. Held on the decision for
    # the cycle that produced it rather than stored, since the stored record is the
    # outcome and the checks are reproducible from the plan and the profile.
    checks: list["GuardrailCheck"] = field(default_factory=list)

    @property
    def approved(self) -> bool:
        return self.decision_type in (
            DecisionType.APPROVE_PLAN,
            DecisionType.APPROVE_ADJUSTMENT,
        )
