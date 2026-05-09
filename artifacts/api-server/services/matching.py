"""
Matching Engine — core da bolsa Krono

Quando uma nova ordem entra, o engine verifica se há
ordens opostas que fecham o negócio:
  - BID encontra ASK mais barato ou igual → transação
  - ASK encontra BID mais caro ou igual → transação

Prioridade: preço melhor primeiro, depois FIFO.
"""

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from models.models import Order, Position, Transaction, MarketPrice, TimeSeries
from models.enums import OrderType, OrderStatus, TransactionType, SeriesStatus


async def match_order(order: Order, db: AsyncSession) -> list[Transaction]:
    transactions = []

    if order.type == OrderType.BID:
        opposite_query = (
            select(Order)
            .where(
                and_(
                    Order.time_series_id == order.time_series_id,
                    Order.type == OrderType.ASK,
                    Order.status == OrderStatus.OPEN,
                    Order.price_hour <= order.price_hour,
                    Order.user_id != order.user_id,
                )
            )
            .order_by(Order.price_hour.asc(), Order.created_at.asc())
        )
    else:
        opposite_query = (
            select(Order)
            .where(
                and_(
                    Order.time_series_id == order.time_series_id,
                    Order.type == OrderType.BID,
                    Order.status == OrderStatus.OPEN,
                    Order.price_hour >= order.price_hour,
                    Order.user_id != order.user_id,
                )
            )
            .order_by(Order.price_hour.desc(), Order.created_at.asc())
        )

    result = await db.execute(opposite_query)
    opposite_orders = result.scalars().all()

    remaining = order.quantity_hours

    for opposite in opposite_orders:
        if remaining <= 0:
            break

        matched_hours = min(remaining, opposite.quantity_hours)
        transaction_price = opposite.price_hour

        bid_order = order if order.type == OrderType.BID else opposite
        ask_order = opposite if order.type == OrderType.BID else order

        is_primary = await _is_primary(order.time_series_id, db)

        tx = Transaction(
            time_series_id=order.time_series_id,
            type=TransactionType.PRIMARY if is_primary else TransactionType.SECONDARY,
            from_user_id=ask_order.user_id,
            to_user_id=bid_order.user_id,
            quantity_hours=matched_hours,
            price_hour=transaction_price,
            payment_mode=bid_order.payment_mode,
            payment_position_id=bid_order.payment_position_id,
            payment_price_type=bid_order.payment_price_type,
            payment_fixed_price=bid_order.payment_fixed_price,
            bid_order_id=bid_order.id,
            ask_order_id=ask_order.id,
            transacted_at=datetime.utcnow(),
        )
        db.add(tx)
        await db.flush()

        mp = MarketPrice(
            time_series_id=order.time_series_id,
            transaction_id=tx.id,
            last_price=transaction_price,
            recorded_at=datetime.utcnow(),
        )
        db.add(mp)

        await _update_positions(
            time_series_id=order.time_series_id,
            from_user_id=ask_order.user_id,
            to_user_id=bid_order.user_id,
            quantity_hours=matched_hours,
            db=db,
        )

        series_result = await db.execute(
            select(TimeSeries).where(TimeSeries.id == order.time_series_id)
        )
        series = series_result.scalar_one()
        if series.status == SeriesStatus.OPEN:
            series.status = SeriesStatus.ACTIVE

        opposite.quantity_hours -= matched_hours
        if opposite.quantity_hours == 0:
            opposite.status = OrderStatus.FILLED

        remaining -= matched_hours
        transactions.append(tx)

    order.quantity_hours = remaining
    if remaining == 0:
        order.status = OrderStatus.FILLED

    return transactions


async def _is_primary(time_series_id: str, db: AsyncSession) -> bool:
    result = await db.execute(
        select(Transaction).where(Transaction.time_series_id == time_series_id).limit(1)
    )
    return result.scalar_one_or_none() is None


async def _update_positions(
    time_series_id: str,
    from_user_id: str,
    to_user_id: str,
    quantity_hours: int,
    db: AsyncSession,
):
    from_result = await db.execute(
        select(Position).where(
            and_(
                Position.time_series_id == time_series_id,
                Position.holder_id == from_user_id,
            )
        )
    )
    from_position = from_result.scalar_one_or_none()
    if from_position:
        from_position.quantity_hours -= quantity_hours
        from_position.updated_at = datetime.utcnow()
        if from_position.quantity_hours <= 0:
            await db.delete(from_position)

    to_result = await db.execute(
        select(Position).where(
            and_(
                Position.time_series_id == time_series_id,
                Position.holder_id == to_user_id,
            )
        )
    )
    to_position = to_result.scalar_one_or_none()
    if to_position:
        to_position.quantity_hours += quantity_hours
        to_position.updated_at = datetime.utcnow()
    else:
        new_position = Position(
            time_series_id=time_series_id,
            holder_id=to_user_id,
            quantity_hours=quantity_hours,
        )
        db.add(new_position)
