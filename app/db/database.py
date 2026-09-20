from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import Base

if settings.database_url.startswith("sqlite:///./"):
    Path("data").mkdir(exist_ok=True)

engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def create_tables() -> None:
    Base.metadata.create_all(engine)


def get_session():
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
