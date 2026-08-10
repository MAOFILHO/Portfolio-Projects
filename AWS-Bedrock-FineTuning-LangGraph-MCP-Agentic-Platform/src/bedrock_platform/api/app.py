from fastapi import FastAPI

from bedrock_platform.api.deps import get_settings
from bedrock_platform.api.insecure_demo_auth import LoginRequest, LoginResponse, verify_demo_login
from bedrock_platform.api.routes import cost, dataset, deploy, finetune, health, infer, scenarios
from bedrock_platform.observability.otel import setup_observability

app = FastAPI(title="AWS Bedrock Fine-Tuning Platform")

# Tracing is wired before any route logic executes.
setup_observability(app, get_settings())

app.include_router(health.router)
app.include_router(scenarios.router)
app.include_router(dataset.router)
app.include_router(finetune.router)
app.include_router(deploy.router)
app.include_router(infer.router)
app.include_router(cost.router)


@app.post("/auth/login", response_model=LoginResponse)
def login(request: LoginRequest) -> LoginResponse:
    return verify_demo_login(request)
