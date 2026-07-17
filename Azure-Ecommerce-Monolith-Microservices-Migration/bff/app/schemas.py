"""Pydantic schemas for the BFF's own first-class endpoints (migration, learn,
metrics). /api/shop/* is intentionally left as an untyped passthrough proxy —
it forwards arbitrary payloads to whichever backend is live, so imposing a
fixed schema there would defeat the point of a generic reverse proxy."""
from typing import Literal

from pydantic import BaseModel

Backend = Literal["monolith", "microservices"]
StepStatus = Literal["pending", "running", "done", "failed"]


class MigrationStep(BaseModel):
    id: str
    title: str
    description: str
    status: StepStatus


class MigrationSnapshot(BaseModel):
    mode: Literal["local", "azure"]
    active_backend: Backend
    running: bool
    last_error: str | None
    steps: list[MigrationStep]


class MigrationStartResponse(BaseModel):
    message: str


class Advantage(BaseModel):
    title: str
    body: str


class AntiPattern(BaseModel):
    name: str
    why: str


class AntiPatterns(BaseModel):
    technical: list[AntiPattern]
    organizational: list[AntiPattern]


class FaqItem(BaseModel):
    q: str
    a: str


class LearnContent(BaseModel):
    advantages: list[Advantage]
    strangler_fig_steps: list[str]
    anti_patterns: AntiPatterns
    glossary: dict[str, str]
    faq: list[FaqItem]


class BenchmarkOperationResult(BaseModel):
    operation: str
    requests: int
    p50_ms: float
    p95_ms: float
    throughput_rps: float
    errors: int


class BenchmarkResult(BaseModel):
    generated_at: str
    measured: list[Literal["monolith", "microservices"]]
    monolith: list[BenchmarkOperationResult]
    microservices: list[BenchmarkOperationResult]
