from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class LogType(str, Enum):
    MEAL = "meal"
    WEIGHT = "weight"
    ACTIVITY = "activity"


@dataclass
class MealLogEntry:
    user_id: int
    timestamp: datetime
    meal_slot: str
    food_description: str
    estimated_kcal: int
    estimated_macros: dict[str, int] = field(default_factory=dict)
    log_id: int | None = None
    type: LogType = LogType.MEAL


@dataclass
class WeightLogEntry:
    user_id: int
    timestamp: datetime
    weight_kg: float
    log_id: int | None = None
    type: LogType = LogType.WEIGHT


@dataclass
class ActivityLogEntry:
    user_id: int
    timestamp: datetime
    activity_type: str
    duration_min: int
    estimated_kcal_burned: int
    log_id: int | None = None
    type: LogType = LogType.ACTIVITY


LogEntry = MealLogEntry | WeightLogEntry | ActivityLogEntry
