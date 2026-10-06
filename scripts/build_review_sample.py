"""Build a blinded sample of system output for expert review.

Each scenario is run under two strategies that produce structurally identical output —
a plan plus feedback — so the only thing distinguishing them is whether the plan was
adapted. The reviewer sees the cases shuffled and unlabelled; the answer key is written
separately and must not be shared with them.
"""

import argparse
import asyncio
import csv
import json
import random
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.tutor import TutorContentAgent  # noqa: E402
from app.config import settings  # noqa: E402
from app.evaluation.scenarios import SCENARIOS  # noqa: E402
from app.evaluation.simulator import Strategy, simulate  # noqa: E402
from app.llm.client import LLMClient  # noqa: E402

REVIEWED_STRATEGIES = (Strategy.ADAPTIVE, Strategy.NON_ADAPTIVE)
OUTPUT_DIR = Path("data/review")
SHUFFLE_SEED = 20261006


async def build_cases(weeks: int, provider: str) -> list[dict]:
    tutor = TutorContentAgent(LLMClient(provider=provider))
    cases: list[dict] = []

    for scenario in SCENARIOS:
        for strategy in REVIEWED_STRATEGIES:
            run = await simulate(scenario, strategy, weeks=weeks)
            plan, assessment, action = run.final_plan, run.final_assessment, run.final_action
            if assessment is None or action is None:
                raise RuntimeError(f"{scenario.name}/{strategy.value} produced no end state")

            print(f"  generating feedback: {scenario.name} / {strategy.value}")
            feedback = await tutor.generate_feedback(action, assessment)

            cases.append(
                {
                    "scenario": scenario.name,
                    "strategy": strategy.value,
                    "profile": {
                        "age": scenario.profile.age,
                        "sex": scenario.profile.sex.value,
                        "height_cm": scenario.profile.height_cm,
                        "start_weight_kg": round(run.start_weight_kg, 1),
                        "current_weight_kg": round(run.final_weight_kg, 1),
                        "activity_level": scenario.profile.activity_level.value,
                        "goal_type": scenario.profile.goal_type.value,
                        "weeks_elapsed": weeks,
                    },
                    "plan": {
                        "calorie_target": plan.calorie_target,
                        "target_weight_kg": plan.target_weight_kg,
                        "macro_targets": asdict(plan.macro_targets),
                        "meal_structure": [asdict(slot) for slot in plan.meal_structure],
                        "version": plan.version,
                    },
                    "observed": {
                        "average_daily_kcal": round(assessment.average_daily_kcal),
                        "adherence_score": round(assessment.adherence_score, 2),
                        "difficulties": assessment.detected_difficulties,
                    },
                    "feedback_text": feedback,
                }
            )
    return cases


def write_outputs(cases: list[dict], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    random.Random(SHUFFLE_SEED).shuffle(cases)

    for index, case in enumerate(cases, start=1):
        case["case_number"] = index

    blinded = [
        {key: value for key, value in case.items() if key not in {"strategy", "scenario"}}
        for case in cases
    ]
    cases_path = out_dir / "cases.json"
    cases_path.write_text(json.dumps(blinded, indent=2), encoding="utf-8")

    key_path = out_dir / "answer_key.csv"
    with key_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_number", "scenario", "strategy"])
        for case in cases:
            writer.writerow([case["case_number"], case["scenario"], case["strategy"]])

    return cases_path, key_path


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weeks", type=int, default=12)
    parser.add_argument("--provider", default="ollama", help="LLM provider for the feedback text")
    args = parser.parse_args()

    # Simulation itself stays on the mock provider: only the feedback shown to the reviewer
    # needs a real model, which keeps this to one generation per case instead of one per week.
    settings.llm_provider = "mock"

    print(f"Building review sample ({args.weeks} weeks, feedback via '{args.provider}')")
    cases = await build_cases(args.weeks, args.provider)
    cases_path, key_path = write_outputs(cases, OUTPUT_DIR)

    print(f"\n{len(cases)} cases written to {cases_path}")
    print(f"Answer key (do NOT share with the reviewer): {key_path}")


if __name__ == "__main__":
    asyncio.run(main())
