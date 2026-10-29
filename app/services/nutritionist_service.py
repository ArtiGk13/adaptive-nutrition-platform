from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db import repository
from app.domain.assessment import AssessmentResult
from app.domain.decisions import DecisionType, SupervisorDecision
from app.domain.nutrition_plan import NutritionPlan
from app.domain.user_profile import Role, UserProfile


@dataclass
class UserOverview:
    profile: UserProfile
    active_plan: NutritionPlan | None
    latest_assessment: AssessmentResult | None
    latest_decision: SupervisorDecision | None

    @property
    def needs_referral(self) -> bool:
        return (
            self.latest_decision is not None
            and self.latest_decision.decision_type == DecisionType.FLAG_REFERRAL
        )


@dataclass
class UserHistory:
    profile: UserProfile
    plans: list[NutritionPlan]
    assessments: list[AssessmentResult]
    decisions: list[SupervisorDecision]


def _last(items: list):
    return items[-1] if items else None


def overview_for(session: Session, profile: UserProfile) -> UserOverview:
    return UserOverview(
        profile=profile,
        active_plan=repository.get_active_plan(session, profile.user_id),
        latest_assessment=_last(repository.get_assessments(session, profile.user_id)),
        latest_decision=_last(repository.get_decisions(session, profile.user_id)),
    )


def list_overviews(session: Session) -> list[UserOverview]:
    """Those being planned for, which excludes the dietitians themselves.

    An overview carries a calorie target, an adherence level and a referral flag. A
    nutritionist account holds none of those, so it arrived in the caseload as a row of
    dashes and zeroes beside the people the dietitian is actually reading about.
    """
    return [
        overview_for(session, profile)
        for profile in repository.list_users(session)
        if profile.role != Role.NUTRITIONIST
    ]


def list_flagged(session: Session) -> list[UserOverview]:
    return [overview for overview in list_overviews(session) if overview.needs_referral]


def get_history(session: Session, user_id: int) -> UserHistory | None:
    profile = repository.get_user(session, user_id)
    if profile is None:
        return None
    return UserHistory(
        profile=profile,
        plans=repository.get_plans(session, user_id),
        assessments=repository.get_assessments(session, user_id),
        decisions=repository.get_decisions(session, user_id),
    )
