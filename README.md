# Adaptive Multi-Agent Platform for Personalised Nutrition & Wellness Planning

Undergraduate thesis implementation: an adaptive multi-agent platform that plans, monitors
and adjusts a personalised nutrition and wellness plan for each user.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts\seed_synthetic_user.py
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/docs and call `POST /users/1/cycle`.

Tests:

```bash
.venv\Scripts\python.exe -m pytest
```

## Architecture

Five agents in a sequential pipeline (`app/agents/coordinator.py`), with no orchestration
framework — state is passed explicitly as arguments and return values:

| Agent | Role | File |
|---|---|---|
| Planner | Initial plan as structured goals (calories, macros, meals) | `app/agents/planner.py` |
| Assessment | Evaluates logged data, detects deviations | `app/agents/assessment.py` |
| Adaptation | Selects the next action or plan revision | `app/agents/adaptation.py` |
| Tutor/Content | Educational content and feedback (the only LLM consumer) | `app/agents/tutor.py` |
| Supervisor | Coordination, safe limits, approval and referral | `app/agents/supervisor.py` |

Flows:

- `run_onboarding`: Planner → Supervisor → plan persisted
- `run_cycle`: Assessment → Adaptation → Supervisor → (persist) → Tutor

### Guardrails

The Supervisor is the **single mandatory checkpoint**: `repository.save_plan()` requires an
approving `SupervisorDecision`, so no code path can persist a plan without review. The rules
are pure functions in `app/agents/guardrails.py`:

- `check_supported_age` — the system targets adults aged 18–65; outside that range it refers
  the user to a specialist, since different reference tables apply over 65 (NEMO, 2019) and
  growth makes them inapplicable under 18
- `check_min_calories` — safe calorie floor per sex
- `check_max_deficit_rate` — maximum permitted deficit as a share of daily expenditure
- `check_macro_distribution` — macros within the acceptable distribution ranges (DRIs, 2010):
  protein 10–35%, fat 20–35%, carbohydrates 45–65% of total energy
- `check_suspicious_pattern` — low BMI combined with a weight-loss goal, rapid weight loss

Every decision is logged (`supervisor` logger) and stored in the `supervisor_decisions` table
for traceability.

### Deterministic logic vs LLM

Nutrition calculations (Mifflin-St Jeor BMR, calorie target, macros), the adaptation rules and
the guardrails are **fully deterministic in code** (`app/domain/`, `app/agents/`). The LLM
(`app/llm/client.py`) is used only to phrase feedback and educational content.

The provider is set in `.env` (`LLM_PROVIDER`). The default is `mock`, which returns canned
text, so the whole system and its tests run without any API key.

### Clinical validation

The clinical assumptions were reviewed by a qualified dietitian (review form in `docs/`).
Confirmed as correct: the Mifflin-St Jeor formula, the calorie floors, the maximum deficit,
and both referral criteria. Two corrections came out of the review and are implemented:

- **Macronutrient distribution** — protein is prescribed per kilogram of body weight, so on a
  reduced calorie target its share of energy inflated and carbohydrates fell below the
  recommended range on **every** weight-loss plan. The distribution is now constrained to the
  DRI (2010) ranges.
- **Age range** — the system performed no age check at all. It is now explicitly limited to
  adults aged 18–65.

**Known limitation:** the meal-level split (breakfast 25% / lunch 35% / dinner 30% / snack 10%)
is the one assumption with no clinical backing — the reviewing dietitian did not recognise
meal distribution as standard practice. It is a presentation default for spreading the daily
target, not a clinical recommendation, and should be described as such.

## Evaluation

```bash
.venv\Scripts\python.exe scripts\run_evaluation.py        # 12 weeks (default)
```

Three strategies are compared on identical synthetic scenarios
([app/evaluation/scenarios.py](app/evaluation/scenarios.py)):

- `adaptive` — the full cycle: assessment, plan adaptation, Supervisor review, feedback
- `non_adaptive` — feedback, but the plan never changes
- `fixed` — a fixed initial plan with no feedback

### Synthetic user model

Each scenario defines a **tolerance**: the largest relative change against daily energy
expenditure that the user can sustain. When the plan demands more, intake drifts back towards
the tolerance boundary and becomes more erratic. Weight is updated from energy balance
(7700 kcal/kg) and expenditure is recalculated daily, so the plateau effect emerges on its own.

The same random seeds are used across all three strategies within a scenario, so differences
are attributable to the system rather than to chance.

**Assumptions to state in the write-up:** the effect of feedback is modelled as a fixed small
improvement in self-regulation (`FEEDBACK_EFFECT`) applied to both `adaptive` and
`non_adaptive`. The `adaptive` − `non_adaptive` difference therefore isolates **plan
adaptation**, and `non_adaptive` − `fixed` isolates feedback.

### Metrics

`mean_adherence`, `consistency`, `suitability` (share of days on which the plan was achievable
for that user), `goal_progress`, `unsafe_weeks` (an independent safety check applied to every
strategy) and `referrals`. `overall_effectiveness` is a weighted sum with explicit weights in
[app/evaluation/metrics.py](app/evaluation/metrics.py).

**Usability** and **content-level quality of the suggestions** are not measured here — they
require the dietitian's expert review.

### Results (12 weeks, 6 scenarios)

| Strategy | Adherence | Consistency | Suitability | Progress | Referrals | Overall |
|---|---|---|---|---|---|---|
| adaptive | 0.94 | 0.89 | **0.74** | 0.68 | 1 | **0.79** |
| non_adaptive | 0.92 | 0.87 | 0.50 | 0.74 | 0 | 0.76 |
| fixed | 0.92 | 0.87 | 0.50 | 0.73 | 0 | 0.75 |

The headline finding is a **trade-off**: the adaptive strategy substantially improves plan
suitability and adherence at the cost of slower progress towards the goal, because it converges
on targets the user can actually sustain instead of insisting on a plan that gets ignored. In
the scenarios where the initial plan was already appropriate (`weight_loss_consistent`,
`maintenance_stable`) the three strategies are identical, as expected. In the safety scenario,
only `adaptive` detected the need for a referral.

## Layout

```
app/
├── domain/      pure dataclasses and nutrition calculations (no DB or API dependency)
├── agents/      the five agents, the guardrails and the coordinator
├── db/          SQLAlchemy models, session, repository (the only ORM <-> domain boundary)
├── llm/         LLM wrapper and prompt templates
├── services/    application layer called by the routes
├── evaluation/  synthetic scenarios, simulation and comparison metrics
└── api/         Pydantic schemas and FastAPI routes
scripts/         synthetic user seeding, evaluation runner
tests/           unit / integration / system
```

## Technologies

Python 3.11+, FastAPI, SQLAlchemy with SQLite, pytest. The database is configured in `.env`
(`DATABASE_URL`); moving to another engine is a connection-string change, not a code change.

## Next steps

- Wire a local LLM provider in `app/llm/client.py`
- Endpoints for the dietitian role (user overview, content management)
- Expert review of usability and of the quality of generated suggestions
