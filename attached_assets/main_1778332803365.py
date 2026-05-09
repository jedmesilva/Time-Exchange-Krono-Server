from contextlib import asynccontextmanager
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import engine, Base, AsyncSessionLocal
from routers.routers import (
    auth_router, users_router, balances_router,
    series_router, positions_router, orders_router,
    transactions_router, market_router,
)
from services.liquidation import run_liquidations

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cria tabelas
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Scheduler de liquidação — roda a cada hora
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
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(balances_router)
app.include_router(series_router)
app.include_router(positions_router)
app.include_router(orders_router)
app.include_router(transactions_router)
app.include_router(market_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "krono"}
