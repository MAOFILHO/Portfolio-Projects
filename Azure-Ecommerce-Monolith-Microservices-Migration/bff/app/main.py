from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .routers import learn, metrics, migration, services, shop

app = FastAPI(
    title="Flask Monolith → Microservices Migration BFF",
    description="Backend-for-frontend orchestrating the monolith, the three microservices, "
                "the live migration engine, benchmark metrics, and Learn page content.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(shop.router)
app.include_router(migration.router)
app.include_router(learn.router)
app.include_router(metrics.router)
app.include_router(services.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "bff"}
