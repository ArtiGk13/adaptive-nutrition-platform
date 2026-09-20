import csv
from pathlib import Path

from app.evaluation.metrics import RunMetrics, compute_metrics
from app.evaluation.scenarios import SCENARIOS, Scenario
from app.evaluation.simulator import DEFAULT_WEEKS, Strategy, simulate

RESULTS_DIR = Path("data/evaluation")


async def run_all(
    scenarios: list[Scenario] | None = None, weeks: int = DEFAULT_WEEKS
) -> list[RunMetrics]:
    results: list[RunMetrics] = []
    for scenario in scenarios or SCENARIOS:
        for strategy in Strategy:
            run = await simulate(scenario, strategy, weeks=weeks)
            results.append(compute_metrics(run))
    return results


def write_csv(results: list[RunMetrics], path: Path | None = None) -> Path:
    target = path or RESULTS_DIR / "results.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0].as_row()))
        writer.writeheader()
        for row in results:
            writer.writerow(row.as_row())
    return target
