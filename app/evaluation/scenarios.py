from dataclasses import dataclass

from app.domain.user_profile import ActivityLevel, GoalType, Sex, UserProfile


@dataclass
class BehaviorProfile:
    """How the synthetic user behaves towards the calorie target.

    tolerance: the largest relative change (deficit or surplus) against daily energy
    expenditure that the user can hold steadily. Plans more demanding than this limit
    lead to compensation and more erratic intake.
    """

    tolerance: float
    noise_ratio: float
    logging_probability: float
    # Systematic deviation from whatever the tolerance model produces, as a proportion of
    # intake. Tolerance alone can only make a user fall short of a demanding plan; this
    # expresses a user who departs from an achievable plan of their own accord, which is
    # the only way to model someone restricting further than they were asked to.
    intake_bias: float = 0.0


@dataclass
class Scenario:
    name: str
    description: str
    profile: UserProfile
    behavior: BehaviorProfile
    goal_weight_kg: float
    seed: int


SCENARIOS: list[Scenario] = [
    Scenario(
        name="weight_loss_consistent",
        description="Weight loss, consistent user with high tolerance for a deficit",
        profile=UserProfile(
            name="Synthetic WL-1",
            age=30,
            sex=Sex.FEMALE,
            height_cm=168.0,
            weight_kg=82.0,
            activity_level=ActivityLevel.LIGHT,
            goal_type=GoalType.WEIGHT_LOSS,
        ),
        behavior=BehaviorProfile(tolerance=0.22, noise_ratio=0.04, logging_probability=0.95),
        goal_weight_kg=76.0,
        seed=11,
    ),
    Scenario(
        name="weight_loss_low_tolerance",
        description="Weight loss, user who cannot sustain an aggressive deficit",
        profile=UserProfile(
            name="Synthetic WL-2",
            age=42,
            sex=Sex.MALE,
            height_cm=178.0,
            weight_kg=95.0,
            activity_level=ActivityLevel.SEDENTARY,
            goal_type=GoalType.WEIGHT_LOSS,
        ),
        behavior=BehaviorProfile(tolerance=0.10, noise_ratio=0.08, logging_probability=0.80),
        goal_weight_kg=88.0,
        seed=22,
    ),
    Scenario(
        name="weight_loss_poor_logging",
        description="Weight loss with incomplete meal logging",
        profile=UserProfile(
            name="Synthetic WL-3",
            age=27,
            sex=Sex.FEMALE,
            height_cm=162.0,
            weight_kg=74.0,
            activity_level=ActivityLevel.MODERATE,
            goal_type=GoalType.WEIGHT_LOSS,
        ),
        behavior=BehaviorProfile(tolerance=0.15, noise_ratio=0.10, logging_probability=0.35),
        goal_weight_kg=68.0,
        seed=33,
    ),
    Scenario(
        name="maintenance_stable",
        description="Weight maintenance with stable behaviour",
        profile=UserProfile(
            name="Synthetic MT-1",
            age=35,
            sex=Sex.MALE,
            height_cm=180.0,
            weight_kg=78.0,
            activity_level=ActivityLevel.MODERATE,
            goal_type=GoalType.MAINTENANCE,
        ),
        behavior=BehaviorProfile(tolerance=0.15, noise_ratio=0.05, logging_probability=0.90),
        goal_weight_kg=78.0,
        seed=44,
    ),
    Scenario(
        name="muscle_gain_steady",
        description="Muscle gain with limited tolerance for a surplus",
        profile=UserProfile(
            name="Synthetic MG-1",
            age=24,
            sex=Sex.MALE,
            height_cm=175.0,
            weight_kg=70.0,
            activity_level=ActivityLevel.ACTIVE,
            goal_type=GoalType.MUSCLE_GAIN,
        ),
        behavior=BehaviorProfile(tolerance=0.08, noise_ratio=0.06, logging_probability=0.85),
        goal_weight_kg=73.0,
        seed=55,
    ),
    Scenario(
        name="weight_loss_over_restricting",
        description="Weight loss where the user restricts further than the plan asks",
        profile=UserProfile(
            name="Synthetic WL-4",
            age=28,
            sex=Sex.FEMALE,
            height_cm=165.0,
            weight_kg=68.0,
            activity_level=ActivityLevel.LIGHT,
            goal_type=GoalType.WEIGHT_LOSS,
        ),
        behavior=BehaviorProfile(
            tolerance=0.25, noise_ratio=0.05, logging_probability=0.90, intake_bias=-0.20
        ),
        goal_weight_kg=61.0,
        seed=77,
    ),
    Scenario(
        name="muscle_gain_low_tolerance",
        description="Muscle gain where the surplus is well beyond what the user sustains",
        profile=UserProfile(
            name="Synthetic MG-2",
            age=26,
            sex=Sex.MALE,
            height_cm=180.0,
            weight_kg=74.0,
            activity_level=ActivityLevel.ACTIVE,
            goal_type=GoalType.MUSCLE_GAIN,
        ),
        behavior=BehaviorProfile(tolerance=0.03, noise_ratio=0.06, logging_probability=0.85),
        goal_weight_kg=77.0,
        seed=88,
    ),
    Scenario(
        name="weight_loss_safety_risk",
        description="Weight loss from an already low weight — safety control scenario",
        profile=UserProfile(
            name="Synthetic RISK-1",
            age=22,
            sex=Sex.FEMALE,
            height_cm=170.0,
            weight_kg=57.0,
            activity_level=ActivityLevel.LIGHT,
            goal_type=GoalType.WEIGHT_LOSS,
        ),
        behavior=BehaviorProfile(tolerance=0.25, noise_ratio=0.03, logging_probability=0.95),
        goal_weight_kg=52.0,
        seed=66,
    ),
]
