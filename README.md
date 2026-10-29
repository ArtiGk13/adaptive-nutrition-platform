# Adaptive Multi-Agent Platform for Personalised Nutrition & Wellness Planning

MSc dissertation implementation: an adaptive multi-agent platform that plans, monitors
and adjusts a personalised nutrition and wellness plan for each user.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts\seed_synthetic_user.py
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000 for the web client, or http://127.0.0.1:8000/docs for the
API documentation, and run an adaptation cycle for the seeded user.

## Web client

A small client is served at the root from `app/static/`: plain HTML, CSS and JavaScript,
with no framework and no build step, so nothing is added to `requirements.txt`. It holds
no logic of its own — it calls the same endpoints any other caller would, and renders the
four stages of a cycle (assessment, adaptation, Supervisor decision, resulting plan) as
they are returned.

Three screens: profile creation, which requests a plan and shows either the plan or the
Supervisor's refusal; the user's own plan, logging and cycle; and the dietitian's view of
every user, those needing referral, and the full decision trail for one user.

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

A second role is supported: an authorised user (the collaborating dietitian) can review every
user's progress and the full Supervisor decision trail through `/nutritionist/*`. The caller is
identified by an `X-User-Id` header and must hold the nutritionist role. This demonstrates role
separation only — there are no credentials, sessions or tokens, and real authentication is
explicitly out of scope for the thesis.

Flows:

- `run_onboarding`: Planner → Supervisor → plan persisted
- `run_cycle`: Assessment → Adaptation → Supervisor → (persist) → Tutor

### Guardrails

The Supervisor is the **single mandatory checkpoint**: `repository.save_plan()` requires an
approving `SupervisorDecision`, so no code path can persist a plan without review. The rules
are pure functions in `app/agents/guardrails.py`:

Checks about the **person** (`run_profile_checks`) run both when a plan is first created and
on every cycle, whether or not a new plan is proposed:

- `check_supported_age` — the system targets adults aged 18–65; outside that range it refers
  the user to a specialist, since different reference tables apply over 65 (NEMO, 2019) and
  growth makes them inapplicable under 18
- `check_declared_conditions` — any declared illness ends the system's involvement and refers
  to a dietitian. Medications are recorded but do not themselves refer, since no such rule was
  given during review
- `check_eating_disorder_signals` — self-reported difficult relationship with food, recent
  weight fluctuation, or perceiving oneself as overweight while underweight. Any single signal
  refers: the system is not a diagnostic instrument, and referring too readily is the safe
  direction of error. These answers may only cause a referral and never influence a plan
- `check_underweight_goal` — BMI below 18.5 combined with a weight-loss goal
- `check_rapid_weight_loss` — logged weight falling faster than 1 kg/week

Checks about the **numbers in a proposed plan** (`run_plan_checks`):

- `check_min_calories` — safe calorie floor per sex
- `check_max_deficit_rate` — maximum permitted deficit as a share of daily expenditure
- `check_macro_distribution` — macros within the acceptable distribution ranges (DRIs, 2010):
  protein 10–35%, fat 20–35%, carbohydrates 45–65% of total energy
- `check_target_weight_reached` — the user has reached the plan's target weight and is still
  pursuing weight loss. Added after the second round of clinical review, which gave two
  instructions that meet in this one condition: stop a user already at their ideal weight who
  seeks further loss, and refer once sustained under-eating has taken weight well below the
  agreed target

Every decision is logged (`supervisor` logger) and stored in the `supervisor_decisions` table
for traceability.

### Deterministic logic vs LLM

Nutrition calculations (Mifflin-St Jeor BMR, calorie target, macros), the adaptation rules and
the guardrails are **fully deterministic in code** (`app/domain/`, `app/agents/`). The LLM
(`app/llm/client.py`) is used only to phrase feedback and educational content.

The provider is set in `.env` (`LLM_PROVIDER`):

- `mock` (default) — canned text, so the whole system and its test suite run with no model
- `ollama` — a model served locally by [Ollama](https://ollama.com), keeping all data on the
  machine. No data is sent to any external service.

```bash
ollama pull qwen2.5:7b
# then set LLM_PROVIDER=ollama in .env
```

Generation is **not on the critical path**: if the model is unreachable, the Tutor logs a
warning and returns no text, while the plan, assessment and Supervisor decision still complete
normally. The test suite forces the `mock` provider regardless of `.env`, so tests never depend
on a running model.

Generating feedback on a local 7B model takes roughly 3–14 seconds depending on whether the
model is already loaded, which is the main cost of keeping inference local.

### Clinical validation

A qualified dietitian reviewed the system in three rounds (both instruments in `docs/`).
Confirmed as correct and unchanged: the Mifflin-St Jeor formula, the calorie floors, the
maximum deficit, and both referral criteria.

**First round — sixteen assumptions on a structured form.** Three defects and one
clarification:

- **Macronutrient distribution** — protein is prescribed per kilogram of body weight, so on a
  reduced calorie target its share of energy inflated and carbohydrates fell below the
  recommended range on **every** weight-loss plan. The distribution is now constrained to the
  DRI (2010) ranges.
- **Age range** — the system performed no age check at all. It is now explicitly limited to
  adults aged 18–65.
- **Medical history** — the system asked nothing about health before issuing a plan. It now
  records allergies, intolerances, conditions, family history, medications and food dislikes,
  and refuses to plan where an illness is declared. A short screening set covering weight
  fluctuation, past dieting and body image was added on the same advice, used only to refer.
- **Target body weight** — the reviewer set out how it is derived and staged, which enabled the
  feature described below. The system had no notion of a target weight before this.

**Second round — four follow-up questions.** The meal split was accepted, and the adaptation
policy was put to her for the first time:

- **The adaptation policy is endorsed in substance and qualified in mechanism.** Asked whether
  a target should be relaxed towards what the user actually eats, she said the target should
  initially be **held**, and relaxed when the user *reports* being unable to follow it or
  *asks* for it to be relaxed, with an explanation that the goal remains reachable over a
  longer period. This system relaxes on inferred behaviour rather than on request, so the
  mechanism differs from the practice it was modelled on. The explanation she specified was
  added to the feedback the Tutor produces when a target is relaxed.
- **A user already at their target weight who seeks further loss should be stopped**, which is
  now `check_target_weight_reached`.

**Third round — blind review of generated output.** Twelve cases, drawn from the adaptive and
non-adaptive configurations, shuffled and unlabelled. One further defect:

- **Target weight was being stated whatever the goal.** Shown a muscle-gain plan, the reviewer
  asked why a user wanting to gain muscle was being told to lose weight: the plan named a
  target of 67.8 kg for a user who weighed 70 kg and was trying to reach 73. A weight derived
  from a desirable BMI describes what a user should come *down* to. Plans now state a target
  weight for weight loss only, and no value is invented for the other goals.

Nothing else was found by any other means: the tests asserted the formula, which was right,
and the evaluation never reads the field.

### Target body weight

A **weight-loss** plan records a `target_weight_kg` derived from a desirable BMI rather than
asking the user to invent a number. The target is **staged**: while the user is overweight or
obese (BMI ≥ 25) the higher initial value applies — 22.4 for women, 22.7 for men — and once
BMI falls below that threshold a regenerated plan moves the target into the desirable range
(21.3–22.1 for women, 21.9–22.4 for men, midpoint used). Both the staging rule and the
values come from the dietitian review.

Maintenance and muscle-gain plans carry **no** target weight (`plan_target_weight` returns
`None`). A weight derived from BMI describes what a user should come down to, so stating it
for someone trying to gain inverts the plan's own objective — the defect the blind review
found. What the target ought to be for those goals is a clinical question the review did not
settle, so none is invented.

**Known limitation:** no body composition analysis, so a target weight cannot distinguish fat
from lean mass. The reviewer raised this about her own answer, and again when reading the
output: for a muscle-gain user, body weight could be held while composition changes.

**Deliberately out of scope:** questions on vomiting, laxative use and purging, which the
reviewer identified as clinically sensitive and beyond what this system should ask. The
eating-disorder screening is therefore partial by design.

The meal split (breakfast 25% / lunch 35% / dinner 30% / snack 10%) was **accepted** in the
second round. The reviewer offered 30% breakfast with 25% dinner as an alternative and added
that the division should ideally follow the user's pattern of activity through the day, which
would require capturing when they are active. That is not implemented.

## Evaluation

```bash
.venv\Scripts\python.exe scripts\run_evaluation.py        # 12 weeks (default)
```

Three strategies are compared on identical synthetic scenarios
([app/evaluation/scenarios.py](app/evaluation/scenarios.py)):

- `adaptive` — the full cycle: assessment, plan adaptation, Supervisor review, feedback
- `non_adaptive` — feedback, but the plan never changes
- `fixed` — a fixed initial plan with no feedback

### Figures

The two figures in the dissertation are generated from the code and the evaluation data
rather than drawn by hand, so neither can drift from what the system actually produced:

```bash
pip install matplotlib        # not a runtime dependency of the application
.venv\Scripts\python.exe scripts\make_figure_4_1.py    # the architecture and its two flows
.venv\Scripts\python.exe scripts\make_figure_6_1.py    # read straight from results.csv
```

Both write a PNG and a PDF at 300 dpi into `docs/figures/`.

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

**Usability** is not measured here. **Content-level quality of the suggestions** is covered by
the blind expert review reported below, not by the simulation.

### Results (12 weeks, 8 scenarios defined, 7 measured)

`weight_loss_safety_risk` begins from a low body weight with a weight-loss goal, and
`check_target_weight_reached` now refuses to plan for that user at all. All three strategies
refuse identically, so the scenario exercises the referral path and yields no run to score. It
is excluded from the averages rather than counted as zero.

| Strategy | Adherence | Consistency | Suitability | Progress | Unsafe weeks | Overall |
|---|---|---|---|---|---|---|
| adaptive | 0.909 | 0.879 | **0.631** | 0.712 | 0 | **0.778** |
| non_adaptive | 0.892 | 0.863 | 0.429 | 0.762 | 0 | 0.748 |
| fixed | 0.890 | 0.862 | 0.429 | 0.743 | 0 | 0.740 |

The headline finding is a **trade-off**: adaptation improves plan suitability and adherence at
the cost of slower progress towards the goal, because it converges on targets the user can
actually sustain instead of insisting on a plan that gets ignored.

Two qualifications matter more than the averages. First, adaptation changes the composite in
only **two** of the seven measured scenarios, `weight_loss_low_tolerance` and
`weight_loss_poor_logging`; the averaged difference comes almost entirely from those. Where
the initial plan was already within the user's tolerance the configurations are
indistinguishable, which is the correct behaviour rather than a null result. Second, the
mechanism is **structurally unreachable for muscle gain**: the behavioural model moves intake
at most a fixed fraction back towards what the user tolerates, so a 10% goal adjustment can
produce an observed deviation of at most 7.3%, below the 8% `BIAS_THRESHOLD`. Expressing the
threshold relative to the goal adjustment would address this.

### Expert review of generated output

Twelve cases rated blind on appropriateness, safety and feedback quality (1–5), plus a
yes/no on whether the reviewer would give the output to a client of her own.

| | Appropriateness | Safety | Feedback | Would give |
|---|---|---|---|---|
| adaptive | 3.50 | 4.33 | 5.00 | 5 of 6 |
| non_adaptive | 4.00 | 4.33 | 4.83 | 4 of 6 |
| all twelve | 3.75 | 4.33 | 4.92 | 9 of 12 |

Read at face value this favours the configuration that does **not** adapt. It cannot be read
that way. Adaptation changes a plan only where a sustained deviation is detected, so four of
the six scenario pairs issued were **numerically identical** across the two configurations and
the twelve cases held only eight distinct plans. The reviewer rated three of those four
identical pairs differently — including opposite yes/no verdicts on plans identical to the
kilocalorie — so two of the three rating points separating the configurations come from pairs
with nothing to separate. The instrument cannot distinguish them; the comparison above rests
on the simulation alone.

What the review did establish: the target-weight defect, independent confirmation of the
defect `check_target_weight_reached` had already closed, and feedback quality of 4.92 from a
7B model running locally, rated 5 in eleven of twelve cases.

## Layout

```
app/
├── domain/      pure dataclasses and nutrition calculations (no DB or API dependency)
├── agents/      the five agents, the guardrails and the coordinator
├── db/          SQLAlchemy models, session, repository (the only ORM <-> domain boundary)
├── llm/         LLM wrapper and prompt templates
├── services/    application layer called by the routes
├── evaluation/  synthetic scenarios, simulation and comparison metrics
├── api/         Pydantic schemas and FastAPI routes
└── static/      the web client: one page, one stylesheet, one script
scripts/         synthetic user seeding, evaluation runner
tests/           unit / integration / system
```

## Technologies

Python 3.11+, FastAPI, SQLAlchemy with SQLite, pytest. The database is configured in `.env`
(`DATABASE_URL`); moving to another engine is a connection-string change, not a code change.

## Next steps

Both items that stood here are done: the adaptation policy has been put to the reviewer, and
the blind review of generated suggestions has returned. What follows from them:

- **Relax a target on request rather than on inference.** There is currently no way for a user
  to report that a plan is unmanageable or to ask for it to be eased. Adding that, and holding
  the target until it is asked for, would align the mechanism with the practice it was modelled
  on — and would turn the comparison above into one between two defensible policies rather than
  one defensible and one approximate.
- **Weight adaptation by the completeness of the record it rests on.** An average drawn from
  40% logging coverage is currently treated as being as informative as one from a near-complete
  record, and `weight_loss_poor_logging` shows the cost in lost progress.
- **Express `BIAS_THRESHOLD` relative to the goal adjustment**, so adaptation is reachable for
  muscle gain.
- **Decide what a target weight should mean for maintenance and muscle gain.** A clinical
  question, not a development one.
- **A blind instrument built from cases known to differ**, with deliberate duplicates included
  to measure the reviewer against herself rather than discovering that by accident.
- **Body composition analysis**, so a target can distinguish fat from lean mass.
- Content management for the dietitian role, once the shape of that content is decided.
