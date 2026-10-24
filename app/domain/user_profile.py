from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Sex(str, Enum):
    MALE = "male"
    FEMALE = "female"


class ActivityLevel(str, Enum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"


class GoalType(str, Enum):
    WEIGHT_LOSS = "weight_loss"
    MAINTENANCE = "maintenance"
    MUSCLE_GAIN = "muscle_gain"


class Role(str, Enum):
    USER = "user"
    NUTRITIONIST = "nutritionist"


@dataclass
class UserProfile:
    name: str
    age: int
    sex: Sex
    height_cm: float
    weight_kg: float
    activity_level: ActivityLevel
    goal_type: GoalType
    user_id: int | None = None
    role: Role = Role.USER
    adherence_level: float = 0.0
    difficulties: list[str] = field(default_factory=list)
    current_plan_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Medical history, in the scope a dietitian identified as the minimum a system should
    # hold before issuing a plan. Declared conditions stop the system; the rest is held
    # for the authorised reviewer and, in future, to constrain food suggestions.
    allergies: list[str] = field(default_factory=list)
    intolerances: list[str] = field(default_factory=list)
    medical_conditions: list[str] = field(default_factory=list)
    family_history: list[str] = field(default_factory=list)
    medications: list[str] = field(default_factory=list)
    food_dislikes: list[str] = field(default_factory=list)

    # Screening signals. These may only cause a referral; they never influence a plan,
    # because interpreting them is a clinical judgement the system does not make.
    recent_weight_fluctuation: bool = False
    difficult_relationship_with_food: bool = False
    perceives_self_as_overweight: bool = False
    previous_diet_attempts: int = 0

    @property
    def bmi(self) -> float:
        height_m = self.height_cm / 100
        return self.weight_kg / (height_m**2)
