from datetime import datetime, timezone

import pytest

USER_PAYLOAD = {
    "name": "API User",
    "age": 30,
    "sex": "female",
    "height_cm": 168.0,
    "weight_kg": 72.0,
    "activity_level": "light",
    "goal_type": "weight_loss",
}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_full_user_flow(client):
    created = client.post("/users", json=USER_PAYLOAD)
    assert created.status_code == 201
    user_id = created.json()["user_id"]

    plan_response = client.post(f"/users/{user_id}/plan")
    assert plan_response.status_code == 201
    plan_body = plan_response.json()
    assert plan_body["supervisor_decision"]["approved"] is True
    calorie_target = plan_body["plan"]["calorie_target"]

    log_response = client.post(
        f"/users/{user_id}/logs/meal",
        json={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "meal_slot": "lunch",
            "food_description": "Chicken salad",
            "estimated_kcal": calorie_target,
        },
    )
    assert log_response.status_code == 201

    cycle_response = client.post(f"/users/{user_id}/cycle")
    assert cycle_response.status_code == 200
    cycle_body = cycle_response.json()
    assert cycle_body["supervisor_decision"]["approved"] is True
    assert cycle_body["action"]["action_type"] == "continue"
    assert cycle_body["assessment"]["adherence_score"] == 1.0


def test_cycle_for_unknown_user_returns_404(client):
    assert client.post("/users/999/cycle").status_code == 404


def test_active_plan_missing_returns_404(client):
    user_id = client.post("/users", json=USER_PAYLOAD).json()["user_id"]
    assert client.get(f"/users/{user_id}/plan").status_code == 404


BAD_PROFILES = [
    ("negative height", {**USER_PAYLOAD, "height_cm": -170.0}),
    ("age of zero", {**USER_PAYLOAD, "age": 0}),
    ("no name at all", {**USER_PAYLOAD, "name": ""}),
]


@pytest.mark.parametrize("label,payload", BAD_PROFILES, ids=[c[0] for c in BAD_PROFILES])
def test_a_profile_that_cannot_describe_a_person_is_refused(client, label, payload):
    """Each of these was accepted and stored. The guardrails then declined to plan for
    some of them, which looks like a safety net and is not one: they weigh what a plan
    would demand of a person, not whether the person was described coherently.

    A weight of two kilos is deliberately absent from this list. It is a possible number
    for a body, and refusing it would be setting a minimum adult weight — the reviewing
    dietitian's call, not this layer's. It reaches the guardrails, which decline to plan
    for it, and that is the right place for it to stop.
    """
    assert client.post("/users", json=payload).status_code == 422, label


def test_a_meal_cannot_carry_negative_energy(client):
    """It entered the daily total and lowered the average the Assessment agent reports
    adherence from, so a single entry could misstate how closely a plan was followed."""
    user_id = client.post("/users", json=USER_PAYLOAD).json()["user_id"]
    response = client.post(f"/users/{user_id}/logs/meal", json={
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meal_slot": "lunch",
        "food_description": "nothing",
        "estimated_kcal": -5000,
    })
    assert response.status_code == 422
