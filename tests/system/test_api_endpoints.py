from datetime import datetime, timezone

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
