from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import get_session
from app.db.models import Base
from app.domain.log_entry import MealLogEntry
from app.domain.user_profile import ActivityLevel, GoalType, Sex, UserProfile


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield test_session
    test_session.close()


@pytest.fixture
def sample_profile() -> UserProfile:
    return UserProfile(
        name="Test User",
        age=30,
        sex=Sex.FEMALE,
        height_cm=168.0,
        weight_kg=72.0,
        activity_level=ActivityLevel.LIGHT,
        goal_type=GoalType.WEIGHT_LOSS,
    )


@pytest.fixture
def meal_logs_factory():
    def build(user_id: int, daily_kcal: int, days: int = 3) -> list[MealLogEntry]:
        now = datetime.now(timezone.utc)
        return [
            MealLogEntry(
                user_id=user_id,
                timestamp=now - timedelta(days=offset),
                meal_slot="lunch",
                food_description="Test meal",
                estimated_kcal=daily_kcal,
            )
            for offset in range(days)
        ]

    return build


@pytest.fixture
def client(session):
    from app.main import app

    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
