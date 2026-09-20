import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.evaluation.metrics import summarise_by_strategy  # noqa: E402
from app.evaluation.runner import run_all, write_csv  # noqa: E402
from app.evaluation.simulator import DEFAULT_WEEKS  # noqa: E402

PER_RUN_HEADER = f"{'scenario':<28}{'strategy':<14}{'adher':>7}{'consist':>9}{'suit':>7}{'progr':>7}{'unsafe':>8}{'ref':>5}{'vers':>6}{'eff':>7}"


def main() -> None:
    weeks = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_WEEKS
    results = asyncio.run(run_all(weeks=weeks))

    print(f"\nΠροσομοίωση {weeks} εβδομάδων ανά σενάριο\n")
    print(PER_RUN_HEADER)
    print("-" * len(PER_RUN_HEADER))
    for row in results:
        print(
            f"{row.scenario:<28}{row.strategy:<14}{row.mean_adherence:>7.2f}"
            f"{row.consistency:>9.2f}{row.suitability:>7.2f}{row.goal_progress:>7.2f}"
            f"{row.unsafe_weeks:>8}{row.referrals:>5}{row.plan_versions:>6}"
            f"{row.overall_effectiveness:>7.2f}"
        )

    print("\nΣύνοψη ανά στρατηγική")
    print("-" * len(PER_RUN_HEADER))
    for strategy, values in summarise_by_strategy(results).items():
        print(f"{strategy:<14} {values}")

    path = write_csv(results)
    print(f"\nΑποτελέσματα: {path}")


if __name__ == "__main__":
    main()
