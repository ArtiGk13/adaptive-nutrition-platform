from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Scope

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


class RevalidatedStatics(StaticFiles):
    """Serve the client without letting a browser hold on to a stale copy.

    There is no build step and so no fingerprint in the filenames: every version of the
    script is served from the same URL. Browsers reuse it, and an edit appears to have
    had no effect — which cost an hour of looking for a fault that was already fixed on
    disk. `no-cache` still allows a conditional request, so an unchanged file is answered
    with 304 and not resent.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


# Mounted last so that it claims only the paths the routers above have not taken.
# The client is static files with no build step: it calls the same endpoints any
# other caller would, and holds no logic of its own.
app.mount("/", RevalidatedStatics(directory=Path(__file__).parent / "static", html=True),
          name="ui")
