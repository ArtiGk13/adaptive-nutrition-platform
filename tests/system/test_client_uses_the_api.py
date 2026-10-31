"""Every endpoint the API publishes is reachable from the client.

The client grew endpoint by endpoint, and three operations stayed unused for a while
without anything saying so: listing users, reading one, and logging activity. This
compares the published paths against the calls in the script, so a new endpoint that
nothing calls, or a call to a path that no longer exists, fails here.
"""

import re
from pathlib import Path

import pytest

CLIENT = Path(__file__).resolve().parents[2] / "app" / "static" / "app.js"


def _calls(script: str) -> list[tuple[str, str]]:
    """The method and path of every api(...) call, with interpolations blanked out."""
    found = []
    verbs = "GET|POST|PUT|PATCH|DELETE"
    for method, path in re.findall(rf'api\(\s*"({verbs})",\s*[`"]([^`"]*)[`"]', script):
        found.append((method, re.sub(r"\$\{[^}]*\}", "{}", path)))
    return found


def _published(app) -> set[tuple[str, str]]:
    operations = set()
    for path, methods in app.openapi()["paths"].items():
        for method in methods:
            operations.add((method.upper(), re.sub(r"\{[^}]*\}", "{}", path)))
    return operations


@pytest.fixture(scope="module")
def script() -> str:
    return CLIENT.read_text(encoding="utf-8")


def test_every_published_endpoint_is_called(script):
    from app.main import app

    called = set(_calls(script))
    # the two overview lists are reached through one helper, by argument
    called |= {("GET", p) for p in ("/nutritionist/users", "/nutritionist/flagged")
               if f'"{p}"' in script}

    unused = sorted(_published(app) - called)
    assert not unused, f"published but never called by the client: {unused}"


def test_the_client_calls_nothing_that_does_not_exist(script):
    from app.main import app

    published = _published(app)
    stray = sorted({c for c in _calls(script) if c not in published})
    assert not stray, f"called by the client but not published: {stray}"
