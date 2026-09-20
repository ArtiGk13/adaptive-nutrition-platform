from dataclasses import dataclass

from app.domain.user_profile import ActivityLevel, GoalType, Sex, UserProfile


@dataclass
class BehaviorProfile:
    """Πώς συμπεριφέρεται ο συνθετικός χρήστης απέναντι στον θερμιδικό στόχο.

    tolerance: η μέγιστη σχετική μεταβολή (έλλειμμα ή πλεόνασμα) ως προς την ημερήσια
    δαπάνη που μπορεί να τηρήσει σταθερά. Πλάνα πιο απαιτητικά από αυτό το όριο
    οδηγούν σε αντιστάθμιση και σε πιο ασταθή πρόσληψη.
    """

    tolerance: float
    noise_ratio: float
    logging_probability: float


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
        description="Απώλεια βάρους, συνεπής χρήστης με υψηλή ανοχή σε έλλειμμα",
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
        description="Απώλεια βάρους, χρήστης που δεν αντέχει επιθετικό έλλειμμα",
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
        description="Απώλεια βάρους με ελλιπή καταγραφή γευμάτων",
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
        description="Διατήρηση βάρους με σταθερή συμπεριφορά",
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
        description="Ενίσχυση μυϊκής μάζας με περιορισμένη ανοχή σε πλεόνασμα",
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
        name="weight_loss_safety_risk",
        description="Απώλεια βάρους από ήδη χαμηλό βάρος — σενάριο ελέγχου ασφάλειας",
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
