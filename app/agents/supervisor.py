from datetime import datetime, timezone

from app.agents.guardrails import (
    GuardrailResult,
    failed,
    run_plan_checks,
    run_profile_checks,
)
from app.domain.decisions import (
    ActionType,
    AdaptationAction,
    DecisionType,
    GuardrailCheck,
    SupervisorDecision,
)
from app.domain.log_entry import LogEntry
from app.domain.nutrition_plan import NutritionPlan
from app.domain.user_profile import UserProfile
from app.logging_config import supervisor_logger


class SupervisorAgent:
    """Mandatory gate: nothing is persisted or returned without a decision from here."""

    async def validate_plan(
        self,
        plan: NutritionPlan,
        profile: UserProfile,
        logs: list[LogEntry] | None = None,
    ) -> SupervisorDecision:
        results = run_profile_checks(profile, logs or []) + run_plan_checks(plan, profile)
        return self._decide(
            profile=profile,
            results=results,
            approved_type=DecisionType.APPROVE_PLAN,
            approved_notes="Initial plan is within safe limits.",
            plan_version=plan.version,
        )

    async def review(
        self, action: AdaptationAction, profile: UserProfile, logs: list[LogEntry]
    ) -> SupervisorDecision:
        results = run_profile_checks(profile, logs)
        if action.new_plan is not None:
            results.extend(run_plan_checks(action.new_plan, profile))

        if action.action_type == ActionType.REFER_SPECIALIST:
            return self._build(
                profile=profile,
                decision_type=DecisionType.FLAG_REFERRAL,
                checks_passed=not failed(results),
                notes="The system action leads to a specialist referral.",
                failed_checks=[result.code for result in failed(results)],
                checks=results,
            )

        return self._decide(
            profile=profile,
            results=results,
            approved_type=DecisionType.APPROVE_ADJUSTMENT,
            approved_notes=f"Approved action '{action.action_type.value}'.",
            plan_version=action.new_plan.version if action.new_plan else None,
        )

    def _decide(
        self,
        profile: UserProfile,
        results: list[GuardrailResult],
        approved_type: DecisionType,
        approved_notes: str,
        plan_version: int | None,
    ) -> SupervisorDecision:
        failures = failed(results)
        if not failures:
            return self._build(
                profile=profile,
                decision_type=approved_type,
                checks_passed=True,
                notes=approved_notes,
                failed_checks=[],
                plan_version=plan_version,
                checks=results,
            )

        referral_codes = {
            "underweight_weight_loss",
            "rapid_weight_loss",
            "age_out_of_range",
            "declared_condition",
            "eating_disorder_signal",
            "target_weight_reached",
        }
        needs_referral = any(failure.code in referral_codes for failure in failures)
        return self._build(
            profile=profile,
            decision_type=DecisionType.FLAG_REFERRAL if needs_referral else DecisionType.HOLD,
            checks_passed=False,
            notes=" ".join(failure.message for failure in failures),
            failed_checks=[failure.code for failure in failures],
            checks=results,
        )

    def _build(
        self,
        profile: UserProfile,
        decision_type: DecisionType,
        checks_passed: bool,
        notes: str,
        failed_checks: list[str],
        plan_version: int | None = None,
        checks: list[GuardrailResult] | None = None,
    ) -> SupervisorDecision:
        decision = SupervisorDecision(
            user_id=profile.user_id,
            cycle_timestamp=datetime.now(timezone.utc),
            decision_type=decision_type,
            guardrail_checks_passed=checks_passed,
            notes=notes,
            failed_checks=failed_checks,
            resulting_plan_version=plan_version,
            checks=[
                GuardrailCheck(code=r.code, passed=r.passed, message=r.message)
                for r in (checks or [])
            ],
        )
        supervisor_logger.info(
            "user=%s decision=%s checks_passed=%s failed=%s notes=%s",
            decision.user_id,
            decision.decision_type.value,
            decision.guardrail_checks_passed,
            decision.failed_checks,
            decision.notes,
        )
        return decision
