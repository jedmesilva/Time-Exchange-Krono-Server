from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import engine, Base, AsyncSessionLocal
from routers.routers import (
    auth_router, users_router, balances_router,
    series_router, positions_router, orders_router,
    transactions_router, market_router, rolls_router,
)
from services.liquidation import run_liquidations

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    scheduler.add_job(
        run_liquidations,
        "interval",
        hours=1,
        args=[AsyncSessionLocal],
        id="liquidation_job",
    )
    scheduler.start()

    yield

    scheduler.shutdown()


app = FastAPI(
    title="Krono",
    description="A bolsa de tempo humano",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api"

app.include_router(auth_router, prefix=PREFIX)
app.include_router(users_router, prefix=PREFIX)
app.include_router(balances_router, prefix=PREFIX)
app.include_router(series_router, prefix=PREFIX)
app.include_router(positions_router, prefix=PREFIX)
app.include_router(orders_router, prefix=PREFIX)
app.include_router(transactions_router, prefix=PREFIX)
app.include_router(market_router, prefix=PREFIX)
app.include_router(rolls_router, prefix=PREFIX)


@app.get("/api/healthz", tags=["health"])
async def health():
    return {"status": "ok", "service": "krono"}
