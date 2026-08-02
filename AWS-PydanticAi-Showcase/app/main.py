"""The umbrella app: a shell page, a sign-in gate, and the demo registry.

Every demo in `app.demos.DEMOS` is mounted at `/api/{demo.id}` behind
`require_session`, and the frontend discovers them at runtime from
`GET /api/demos` — so adding a demo means writing its package and appending it
to `DEMOS`, with no changes here and none to the nav.

All four demos share one process, one container, one ECS task, and one load
balancer. That's the whole point: four apps, no growth in AWS footprint.
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()  # must run before importing app.demos, which constructs agents eagerly

from pathlib import Path  # noqa: E402

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from .auth import (  # noqa: E402
    SESSION_COOKIE,
    authenticate,
    issue_session,
    read_session,
    require_session,
)
from .demos import DEMOS  # noqa: E402

app = FastAPI(title="Contoso AI Showcase")

STATIC_DIR = Path(__file__).parent / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def no_static_cache(request: Request, call_next):
    """This app is under active iteration; a redeploy should be visible on
    the next page load, not after everyone's browser cache happens to expire.
    `StaticFiles` sends no `Cache-Control` of its own, so absent this,
    browsers apply heuristic caching and can silently keep serving JS/CSS
    from before the last deploy."""
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response


for demo in DEMOS:
    app.include_router(
        demo.router,
        prefix=f"/api/{demo.id}",
        tags=[demo.id],
        dependencies=[Depends(require_session)],
    )


class LoginRequest(BaseModel):
    username: str
    password: str


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    # This app is under active iteration; without this, browsers can cache a
    # stale copy of the shell and silently serve old behavior.
    return HTMLResponse(
        (STATIC_DIR / "index.html").read_text(), headers={"Cache-Control": "no-store"}
    )


@app.get("/api/demos")
async def list_demos(_: str = Depends(require_session)) -> list[dict[str, str]]:
    return [demo.summary() for demo in DEMOS]


@app.post("/api/login")
async def login(request: LoginRequest, response: Response) -> dict[str, str]:
    if not authenticate(request.username, request.password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    response.set_cookie(
        SESSION_COOKIE,
        issue_session(request.username.strip().lower()),
        httponly=True,
        samesite="lax",
        # Not `secure=True`: the demo ALB is HTTP-only (no ACM certificate, so
        # no domain purchase needed), and a Secure cookie would never be sent.
        # Turn this on the moment there's an HTTPS listener.
    )
    return {"username": request.username.strip().lower()}


@app.post("/api/logout")
async def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(SESSION_COOKIE)
    return {"signed_out": True}


@app.get("/api/session")
async def session(showcase_session: str | None = Cookie(default=None)) -> dict[str, str | None]:
    """Who (if anyone) is signed in — the shell calls this on load to decide
    whether to render the sign-in screen or the demo nav."""
    return {"username": read_session(showcase_session)}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
