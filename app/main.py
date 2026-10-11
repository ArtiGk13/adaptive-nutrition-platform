from fastapi import FastAPI

from app.api.routes import cycle, logs, nutritionist, plans, users
from app.db.database import create_tables
from app.logging_config import setup_logging

setup_logging()
create_tables()

app = FastAPI(
    title="Adaptive Multi-Agent Nutrition & Wellness Platform",
    version="0.1.0",
)

app.include_router(users.router)
app.include_router(plans.router)
app.include_router(logs.router)
app.include_router(cycle.router)
app.include_router(nutritionist.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
