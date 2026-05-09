"""
Liquidation Service

Roda periodicamente via scheduler.
Para cada série ACTIVE com expires_at no passado:

  1. Para cada posição (incluindo carteira própria do emissor):
     - Debita o emissor pelo valor da posição
     - Credita o titular pelo mesmo valor
     - Registra Transaction LIQUIDATION
     - Atualiza MarketPrice

  2. Rolagem automática — se houver série seguinte do emissor disponível:
     - Debita titular pelo preço da série seguinte
     - Credita emissor pelo mesmo valor
     - Atualiza Position para série seguinte
     - Registra Transaction SECONDARY
     - Registra Roll com spread realizado

  3. Status → LIQUIDATED se saldo do emissor >= 0, EXPIRED se negativo

  4. Aplica juros sobre saldos negativos
"""

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select, and_
from models.models import TimeSeries, Position, Balance, MarketPrice, Transaction, Roll
from models.enums import SeriesStatus, TransactionType, PaymentMode
from config import settings


async def run_liquidations(session_factory: async_sessionmaker):
    async with session_factory() as db:
        try:
            await _process_expired_series(db)
            await _apply_debt_interest(db)
            await db.commit()
        except Exception as e:
            await db.rollback()
            print(f"[liquidation] erro: {e}")


async def _process_expired_series(db: AsyncSession):
    now = datetime.utcnow()
    result = await db.execute(
        select(TimeSeries).where(
            and_(
                TimeSeries.status == SeriesStatus.ACTIVE,
                TimeSeries.expires_at <= now,
            )
        )
    )
    series_list = result.scalars().all()
    for series in series_list:
        await _liquidate_series(series, db)


async def _liquidate_series(series: TimeSeries, db: AsyncSession):
    last_price = await _get_last_price(series.id, db)
    repurchase_price = (
        float(series.repurchase_price)
        if series.repurchase_type.value == "FIXED"
        else last_price
    )

    if repurchase_price is None:
        print(f"[liquidation] série {series.id} sem preço de mercado — ignorando")
        return

    next_series = await _get_next_series(series, db)
    next_price = await _get_last_price(next_series.id, db) if next_series else None

    positions_result = await db.execute(
        select(Position).where(Position.time_series_id == series.id)
    )
    positions = positions_result.scalars().all()

    issuer_balance = await _get_or_create_balance(series.issuer_id, db)

    for position in positions:
        liquidation_value = float(position.quantity_hours) * repurchase_price

        issuer_balance.amount = float(issuer_balance.amount) - liquidation_value
        issuer_balance.updated_at = datetime.utcnow()

        holder_balance = await _get_or_create_balance(position.holder_id, db)
        holder_balance.amount = float(holder_balance.amount) + liquidation_value
        holder_balance.updated_at = datetime.utcnow()

        liq_tx = Transaction(
            time_series_id=series.id,
            type=TransactionType.LIQUIDATION,
            from_user_id=series.issuer_id,
            to_user_id=position.holder_id,
            quantity_hours=position.quantity_hours,
            price_hour=repurchase_price,
            payment_mode=PaymentMode.MONEY,
            transacted_at=datetime.utcnow(),
        )
        db.add(liq_tx)
        await db.flush()

        db.add(MarketPrice(
            time_series_id=series.id,
            transaction_id=liq_tx.id,
            last_price=repurchase_price,
            recorded_at=datetime.utcnow(),
        ))

        if next_series and next_price:
            roll_value = float(position.quantity_hours) * next_price
            spread = round(next_price - repurchase_price, 4)

            holder_balance.amount = float(holder_balance.amount) - roll_value
            holder_balance.updated_at = datetime.utcnow()

            issuer_balance.amount = float(issuer_balance.amount) + roll_value
            issuer_balance.updated_at = datetime.utcnow()

            await _update_position(
                time_series_id=next_series.id,
                holder_id=position.holder_id,
                quantity_hours=position.quantity_hours,
                db=db,
            )

            roll_tx = Transaction(
                time_series_id=next_series.id,
                type=TransactionType.SECONDARY,
                from_user_id=series.issuer_id,
                to_user_id=position.holder_id,
                quantity_hours=position.quantity_hours,
                price_hour=next_price,
                payment_mode=PaymentMode.MONEY,
                transacted_at=datetime.utcnow(),
            )
            db.add(roll_tx)
            await db.flush()

            db.add(MarketPrice(
                time_series_id=next_series.id,
                transaction_id=roll_tx.id,
                last_price=next_price,
                recorded_at=datetime.utcnow(),
            ))

            db.add(Roll(
                issuer_id=series.issuer_id,
                holder_id=position.holder_id,
                from_series_id=series.id,
                from_price=repurchase_price,
                to_series_id=next_series.id,
                to_price=next_price,
                quantity_hours=position.quantity_hours,
                roll_spread=spread,
                rolled_at=datetime.utcnow(),
            ))

            print(
                f"[roll] {position.holder_id[:8]} "
                f"{series.id[:8]} → {next_series.id[:8]} "
                f"spread={spread:+.2f}"
            )

    series.status = (
        SeriesStatus.LIQUIDATED
        if float(issuer_balance.amount) >= 0
        else SeriesStatus.EXPIRED
    )
    print(f"[liquidation] série {series.id[:8]} → {series.status.value}")


async def _get_next_series(series: TimeSeries, db: AsyncSession) -> TimeSeries | None:
    result = await db.execute(
        select(TimeSeries).where(
            and_(
                TimeSeries.issuer_id == series.issuer_id,
                TimeSeries.expires_at > series.expires_at,
                TimeSeries.status.in_([SeriesStatus.OPEN, SeriesStatus.ACTIVE]),
            )
        ).order_by(TimeSeries.expires_at.asc()).limit(1)
    )
    return result.scalar_one_or_none()


async def _update_position(
    time_series_id: str,
    holder_id: str,
    quantity_hours: int,
    db: AsyncSession,
):
    result = await db.execute(
        select(Position).where(
            and_(
                Position.time_series_id == time_series_id,
                Position.holder_id == holder_id,
            )
        )
    )
    position = result.scalar_one_or_none()
    if position:
        position.quantity_hours += quantity_hours
        position.updated_at = datetime.utcnow()
    else:
        db.add(Position(
            time_series_id=time_series_id,
            holder_id=holder_id,
            quantity_hours=quantity_hours,
        ))


async def _apply_debt_interest(db: AsyncSession):
    result = await db.execute(select(Balance).where(Balance.amount < 0))
    for balance in result.scalars().all():
        interest = abs(float(balance.amount)) * settings.debt_interest_rate
        balance.debt_interest = float(balance.debt_interest) + interest
        balance.amount = float(balance.amount) - interest
        balance.updated_at = datetime.utcnow()


async def _get_last_price(time_series_id: str, db: AsyncSession) -> float | None:
    result = await db.execute(
        select(MarketPrice)
        .where(MarketPrice.time_series_id == time_series_id)
        .order_by(MarketPrice.recorded_at.desc())
        .limit(1)
    )
    mp = result.scalar_one_or_none()
    return float(mp.last_price) if mp else None


async def _get_or_create_balance(user_id: str, db: AsyncSession) -> Balance:
    result = await db.execute(select(Balance).where(Balance.user_id == user_id))
    balance = result.scalar_one_or_none()
    if not balance:
        balance = Balance(user_id=user_id)
        db.add(balance)
        await db.flush()
    return balance
