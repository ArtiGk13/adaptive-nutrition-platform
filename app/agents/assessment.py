from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from app.domain.assessment import AssessmentFlag, AssessmentResult
from app.domain.log_entry import LogEntry, MealLogEntry
from app.domain.nutrition_plan import NutritionPlan
from app.domain.user_profile import UserProfile

DEVIATION_THRESHOLD = 0.15
GOOD_ADHERENCE = 0.80
WEAK_ADHERENCE = 0.50
BIAS_THRESHOLD = 0.08
ASSESSMENT_WINDOW_DAYS = 14


def _naive(moment: datetime) -> datetime:
    return moment.replace(tzinfo=None) if moment.tzinfo else moment


class AssessmentAgent:
    """Scores adherence of logged meals against the active plan. Deterministic."""

    async def evaluate(
        self, profile: UserProfile, plan: NutritionPlan, logs: list[LogEntry]
    ) -> AssessmentResult:
        daily_kcal = self._daily_intake(self._recent(logs))

        if not daily_kcal:
            return AssessmentResult(
                user_id=profile.user_id,
                plan_id=plan.plan_id,
                timestamp=datetime.now(timezone.utc),
                adherence_score=0.0,
                average_daily_kcal=0.0,
                deviations=[],
                detected_difficulties=["Δεν υπάρχει καταγραφή γευμάτων."],
                proposed_flag=AssessmentFlag.EXTRA_SUPPORT,
            )

        target = plan.calorie_target
        deviations: list[str] = []
        daily_scores: list[float] = []

        for day, kcal in sorted(daily_kcal.items()):
            relative_gap = abs(kcal - target) / target
            daily_scores.append(max(0.0, 1.0 - relative_gap))
            if relative_gap > DEVIATION_THRESHOLD:
                direction = "υπέρβαση" if kcal > target else "υστέρηση"
                deviations.append(f"{day.isoformat()}: {kcal} kcal ({direction} {relative_gap:.0%})")

        adherence_score = sum(daily_scores) / len(daily_scores)
        average_daily_kcal = sum(daily_kcal.values()) / len(daily_kcal)

        return AssessmentResult(
            user_id=profile.user_id,
            plan_id=plan.plan_id,
            timestamp=datetime.now(timezone.utc),
            adherence_score=adherence_score,
            average_daily_kcal=average_daily_kcal,
            deviations=deviations,
            detected_difficulties=self._difficulties(average_daily_kcal, target, deviations),
            proposed_flag=self._flag(adherence_score, (average_daily_kcal - target) / target),
        )

    def _recent(self, logs: list[LogEntry]) -> list[LogEntry]:
        """Only the current window matters — older logs describe a superseded plan."""
        if not logs:
            return []
        cutoff = max(_naive(entry.timestamp) for entry in logs) - timedelta(
            days=ASSESSMENT_WINDOW_DAYS
        )
        return [entry for entry in logs if _naive(entry.timestamp) >= cutoff]

    def _daily_intake(self, logs: list[LogEntry]) -> dict[date, int]:
        totals: dict[date, int] = defaultdict(int)
        for entry in logs:
            if isinstance(entry, MealLogEntry):
                totals[entry.timestamp.date()] += entry.estimated_kcal
        return dict(totals)

    def _difficulties(
        self, average_daily_kcal: float, target: int, deviations: list[str]
    ) -> list[str]:
        difficulties: list[str] = []
        gap = (average_daily_kcal - target) / target
        if gap > DEVIATION_THRESHOLD:
            difficulties.append("Συστηματική υπέρβαση του θερμιδικού στόχου.")
        elif gap < -DEVIATION_THRESHOLD:
            difficulties.append("Συστηματική υστέρηση από τον θερμιδικό στόχο.")
        if len(deviations) >= 3:
            difficulties.append("Χαμηλή συνέπεια στην τήρηση του πλάνου.")
        return difficulties

    def _flag(self, adherence_score: float, bias_ratio: float) -> AssessmentFlag:
        if adherence_score < WEAK_ADHERENCE:
            return AssessmentFlag.EXTRA_SUPPORT
        # A steady one-directional gap means the plan itself is off, even when the
        # magnitude of each day's deviation still scores as acceptable adherence.
        if abs(bias_ratio) > BIAS_THRESHOLD:
            return AssessmentFlag.ADJUST
        if adherence_score >= GOOD_ADHERENCE:
            return AssessmentFlag.CONTINUE
        return AssessmentFlag.ADJUST
