from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AssessmentFlag(str, Enum):
    CONTINUE = "continue"
    ADJUST = "adjust"
    EXTRA_SUPPORT = "extra_support"
    REFER_SPECIALIST = "refer_specialist"


@dataclass
class AssessmentResult:
    user_id: int
    plan_id: int
    timestamp: datetime
    adherence_score: float
    average_daily_kcal: float
    proposed_flag: AssessmentFlag
    deviations: list[str] = field(default_factory=list)
    detected_difficulties: list[str] = field(default_factory=list)
    assessment_id: int | None = None
