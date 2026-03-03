from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import User
from handlers.button_helper import answer_with_content
from keyboards.main import back_to_menu_kb
from config import config

router = Router()


@router.callback_query(lambda c: c.data == "menu:earn")
async def cb_earn(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    ref_link = f"https://t.me/{config.BOT_USERNAME}?start=ref_{db_user.user_id}"
    default_text = (
        "⭐ <b>Заработать звёзды</b>\n\n"
        "Приглашай друзей и получай <b>Telegram Stars</b> за каждого нового участника!\n\n"
        "💰 <b>Сколько платим:</b>\n"
        "• За каждого реферала — <b>4–6 ⭐</b>\n"
        "• Один пользователь засчитывается только один раз\n"
        "• Выплата мгновенная — сразу после регистрации друга\n\n"
        "📤 <b>Как пригласить:</b>\n"
        "Отправь ссылку другу в личку, в чат или опубликуй в социальных сетях\n\n"
        f"🔗 <b>Твоя реферальная ссылка:</b>\n<code>{ref_link}</code>"
    )
    await answer_with_content(callback, session, "menu:earn", default_text, back_to_menu_kb())
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu:referrals")
async def cb_referrals(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    result = await session.execute(
        select(User).where(User.referrer_id == db_user.user_id)
    )
    refs = result.scalars().all()

    lines = []
    for ref in refs[:20]:
        name = ref.first_name or "—"
        uname = f"@{ref.username}" if ref.username else ""
        lines.append(f"• {name} {uname}")

    body = "\n".join(lines) if lines else "Рефералов пока нет."
    default_text = (
        f"👥 <b>Мои рефералы</b>\n\n"
        f"Всего: <b>{db_user.referrals_count}</b>\n\n"
        f"{body}"
    )
    await answer_with_content(callback, session, "menu:referrals", default_text, back_to_menu_kb())
    await callback.answer()


@router.callback_query(lambda c: c.data == "menu:how")
async def cb_how(callback: CallbackQuery, session: AsyncSession) -> None:
    default_text = (
        "ℹ️ <b>Как это работает</b>\n\n"
        "1. Получи свою реферальную ссылку в разделе «⭐ Заработать звёзды»\n"
        "2. Отправь ссылку друзьям\n"
        "3. Когда друг запустит бота — тебе начислятся Telegram Stars\n"
        "4. Накопи нужную сумму и выведи через «💰 Вывод»\n\n"
        "🎁 Не забывай получать ежедневный бонус!\n"
        "🎟 Используй промокоды для дополнительных звёзд."
    )
    await answer_with_content(callback, session, "menu:how", default_text, back_to_menu_kb())
    await callback.answer()
