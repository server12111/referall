from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database.models import User, Lottery, LotteryTicket
from handlers.button_helper import safe_edit
from keyboards.lottery import lottery_menu_kb

router = Router()

TICKET_PRICE = 5.0
LOTTERY_REF_REQUIRED = 2
COMMISSION = 0.30  # 30% hidden from users


async def _get_active_lottery(session: AsyncSession) -> Lottery | None:
    result = await session.execute(
        select(Lottery).where(Lottery.status == "active").order_by(Lottery.id.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def _get_user_ticket_count(session: AsyncSession, lottery_id: int, user_id: int) -> int:
    result = await session.execute(
        select(func.count(LotteryTicket.id)).where(
            LotteryTicket.lottery_id == lottery_id,
            LotteryTicket.user_id == user_id,
        )
    )
    return result.scalar() or 0


def _lottery_text(lottery: Lottery, user_tickets: int, balance: float) -> str:
    return (
        "🎟 <b>Лотерея</b>\n\n"
        f"💰 <b>Призовой пул: {lottery.prize_pool:.2f} ⭐</b>\n"
        f"🎫 Продано билетов: <b>{lottery.tickets_sold}</b>\n\n"
        "🗓 Розыгрыш: <b>в субботу</b>\n\n"
        "📋 <b>Условия участия:</b>\n"
        f"• Цена билета: <b>{TICKET_PRICE:.0f} ⭐</b>\n"
        f"• Минимум рефералов: <b>{LOTTERY_REF_REQUIRED}</b>\n\n"
        f"🎫 Твоих билетов: <b>{user_tickets}</b>\n"
        f"💳 Твой баланс: <b>{balance:.2f} ⭐</b>"
    )


@router.callback_query(lambda c: c.data == "game:lottery")
async def cb_lottery(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    lottery = await _get_active_lottery(session)

    if lottery is None:
        await safe_edit(
            callback,
            "🎟 <b>Лотерея</b>\n\nЛотерея пока не запущена. Ожидайте объявления!",
            lottery_menu_kb(False),
        )
        await callback.answer()
        return

    user_tickets = await _get_user_ticket_count(session, lottery.id, db_user.user_id)
    can_buy = (
        db_user.referrals_count >= LOTTERY_REF_REQUIRED
        and db_user.stars_balance >= TICKET_PRICE
    )

    await safe_edit(callback, _lottery_text(lottery, user_tickets, db_user.stars_balance), lottery_menu_kb(can_buy))
    await callback.answer()


@router.callback_query(lambda c: c.data == "game:lottery_buy")
async def cb_lottery_buy(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    if db_user.referrals_count < LOTTERY_REF_REQUIRED:
        await callback.answer(
            f"❌ Нужно минимум {LOTTERY_REF_REQUIRED} реферала.\n"
            f"У тебя: {db_user.referrals_count}/{LOTTERY_REF_REQUIRED}",
            show_alert=True,
        )
        return

    if db_user.stars_balance < TICKET_PRICE:
        await callback.answer(
            f"❌ Недостаточно звёзд. Нужно {TICKET_PRICE:.0f} ⭐",
            show_alert=True,
        )
        return

    lottery = await _get_active_lottery(session)
    if lottery is None:
        await callback.answer("❌ Лотерея не активна.", show_alert=True)
        return

    # Deduct ticket price and update lottery
    db_user.stars_balance -= TICKET_PRICE
    prize_addition = round(TICKET_PRICE * (1 - COMMISSION), 2)
    lottery.tickets_sold += 1
    lottery.total_collected = round(lottery.total_collected + TICKET_PRICE, 2)
    lottery.prize_pool = round(lottery.prize_pool + prize_addition, 2)
    session.add(LotteryTicket(lottery_id=lottery.id, user_id=db_user.user_id))
    await session.commit()

    user_tickets = await _get_user_ticket_count(session, lottery.id, db_user.user_id)
    can_buy = db_user.stars_balance >= TICKET_PRICE

    await safe_edit(
        callback,
        "✅ <b>Билет куплен!</b>\n\n" + _lottery_text(lottery, user_tickets, db_user.stars_balance),
        lottery_menu_kb(can_buy),
    )
    await callback.answer(f"✅ Билет куплен! (-{TICKET_PRICE:.0f} ⭐)")
