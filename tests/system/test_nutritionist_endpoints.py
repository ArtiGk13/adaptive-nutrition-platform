from datetime import datetime, timezone

import pytest

USER_PAYLOAD = {
    "name": "Regular User",
    "age": 30,
    "sex": "female",
    "height_cm": 168.0,
    "weight_kg": 82.0,
    "activity_level": "light",
    "goal_type": "weight_loss",
}

NUTRITIONIST_PAYLOAD = {**USER_PAYLOAD, "name": "Dietitian", "role": "nutritionist"}

UNDERWEIGHT_PAYLOAD = {
    **USER_PAYLOAD,
    "name": "Referral Case",
    "weight_kg": 48.0,
    "goal_type": "weight_loss",
}


@pytest.fixture
def nutritionist_id(client) -> int:
    return client.post("/users", json=NUTRITIONIST_PAYLOAD).json()["user_id"]


@pytest.fixture
def user_id(client) -> int:
    created = client.post("/users", json=USER_PAYLOAD).json()["user_id"]
    client.post(f"/users/{created}/plan")
    return created


def auth(user_id: int) -> dict:
    return {"X-User-Id": str(user_id)}


def test_missing_header_is_rejected(client):
    assert client.get("/nutritionist/users").status_code == 422


def test_unknown_caller_is_rejected(client):
    assert client.get("/nutritionist/users", headers=auth(999)).status_code == 401


def test_regular_user_is_forbidden(client, user_id):
    response = client.get("/nutritionist/users", headers=auth(user_id))
    assert response.status_code == 403


def test_nutritionist_sees_user_overviews(client, nutritionist_id, user_id):
    response = client.get("/nutritionist/users", headers=auth(nutritionist_id))
    assert response.status_code == 200

    overview = next(row for row in response.json() if row["user_id"] == user_id)
    assert overview["calorie_target"] > 0
    assert overview["target_weight_kg"] > 0
    assert overview["needs_referral"] is False


def test_history_exposes_the_supervisor_decision_trail(client, nutritionist_id, user_id):
    client.post(
        f"/users/{user_id}/logs/meal",
        json={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "meal_slot": "lunch",
            "food_description": "Chicken salad",
            "estimated_kcal": 1900,
        },
    )
    client.post(f"/users/{user_id}/cycle")

    body = client.get(f"/nutritionist/users/{user_id}", headers=auth(nutritionist_id)).json()

    assert body["profile"]["user_id"] == user_id
    assert len(body["plans"]) >= 1
    assert len(body["assessments"]) == 1
    assert len(body["decisions"]) >= 2
    assert all("decision_type" in decision for decision in body["decisions"])


def test_history_for_unknown_user_is_404(client, nutritionist_id):
    assert client.get("/nutritionist/users/999", headers=auth(nutritionist_id)).status_code == 404


def test_flagged_list_contains_referred_users(client, nutritionist_id):
    referred = client.post("/users", json=UNDERWEIGHT_PAYLOAD).json()["user_id"]
    client.post(f"/users/{referred}/plan")

    flagged = client.get("/nutritionist/flagged", headers=auth(nutritionist_id)).json()

    assert [row["user_id"] for row in flagged] == [referred]
    assert flagged[0]["needs_referral"] is True


DIETITIAN = {
    "name": "A Dietitian",
    "age": 40,
    "sex": "female",
    "height_cm": 170.0,
    "weight_kg": 65.0,
    "activity_level": "moderate",
    "goal_type": "maintenance",
    "role": "nutritionist",
}

PLAN_HOLDER = {
    "name": "A User",
    "age": 30,
    "sex": "female",
    "height_cm": 165.0,
    "weight_kg": 72.0,
    "activity_level": "light",
    "goal_type": "weight_loss",
}


def test_the_caseload_excludes_the_dietitians(client):
    """An overview carries a target, an adherence level and a referral flag, and a
    nutritionist account holds none of them. Listing them put rows of dashes beside the
    people the dietitian is reading about."""
    caller = client.post("/users", json=DIETITIAN).json()["user_id"]
    colleague = client.post("/users", json=DIETITIAN).json()["user_id"]
    planned_for = client.post("/users", json=PLAN_HOLDER).json()["user_id"]

    listed = client.get("/nutritionist/users", headers={"X-User-Id": str(caller)}).json()
    ids = [row["user_id"] for row in listed]

    assert planned_for in ids
    assert caller not in ids
    assert colleague not in ids
