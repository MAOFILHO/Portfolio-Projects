# ============================================================================
# DELIBERATE INSECURE STUB — NOT REAL AUTHENTICATION.
# Hardcoded demo/demo123 credentials. No Cognito, no IAM, no token issuance,
# no session store. Exists only so the demo has a login screen. Never wire
# this to a real identity provider.
# ============================================================================

from pydantic import BaseModel, ConfigDict

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo123"


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authenticated: bool
    note: str = "Demo credentials — not real authentication."


def verify_demo_login(request: LoginRequest) -> LoginResponse:
    ok = request.username == DEMO_USERNAME and request.password == DEMO_PASSWORD
    return LoginResponse(authenticated=ok)
