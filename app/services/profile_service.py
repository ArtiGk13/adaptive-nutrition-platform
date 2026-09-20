from sqlalchemy.orm import Session

from app.db import repository
from app.domain.log_entry import LogEntry
from app.domain.user_profile import UserProfile


def create_profile(session: Session, profile: UserProfile) -> UserProfile:
    return repository.create_user(session, profile)


def get_profile(session: Session, user_id: int) -> UserProfile | None:
    return repository.get_user(session, user_id)


def list_profiles(session: Session) -> list[UserProfile]:
    return repository.list_users(session)


def add_log(session: Session, entry: LogEntry) -> LogEntry:
    return repository.add_log_entry(session, entry)


def get_logs(session: Session, user_id: int) -> list[LogEntry]:
    return repository.get_logs(session, user_id)
