from datetime import datetime, timedelta

from aiogram import Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from database.models import User
from handlers.button_helper import answer_with_content, safe_edit
from keyboards.top import top_menu_kb, top_period_kb, top_result_kb

router = Router()

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
NUMBERS = {4: "4️⃣", 5: "5️⃣", 6: "6️⃣", 7: "7️⃣", 8: "8️⃣", 9: "9️⃣", 10: "🔟"}

PERIOD_LABELS = {
    "day":   "сегодня",
    "week":  "7 дней",
    "month": "30 дней",
    "all":   "всё время",
}
PERIOD_DAYS = {"day": 1, "week": 7, "month": 30, "all": None}


def _format_pos(pos: int) -> str:
    return MEDALS.get(pos) or NUMBERS.get(pos) or f"{pos}."


# ─── Entry: show type selection ───────────────────────────────────────────────

@router.callback_query(lambda c: c.data == "menu:top")
async def cb_top_menu(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    default_text = (
        "🏆 <b>Топ пользователей</b>\n\n"
        f"💰 Ваш баланс: <b>{db_user.stars_balance:.2f} ⭐</b>\n"
        f"👥 Ваши рефералы: <b>{db_user.referrals_count}</b>\n\n"
        "Выбери категорию:"
    )
    await answer_with_content(callback, session, "menu:top", default_text, top_menu_kb())
    await callback.answer()


# ─── Period selection ─────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("top:type:"))
async def cb_top_type(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    top_type = callback.data.split(":")[2]  # "refs" or "stars"

    if top_type == "refs":
        title = "👥 Топ по рефералам"
        desc = "Рейтинг по количеству приглашённых пользователей."
        key = "top:refs"
    else:
        title = "⭐ Топ по звёздам"
        desc = "Рейтинг по балансу звёзд."
        key = "top:stars"

    default_text = f"{title}\n\n{desc}\n\nВыбери период:"
    await answer_with_content(callback, session, key, default_text, top_period_kb(top_type))
    await callback.answer()


# ─── Top results ──────────────────────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("top:refs:"))
async def cb_top_refs(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    period = callback.data.split(":")[2]
    period_label = PERIOD_LABELS.get(period, period)
    days = PERIOD_DAYS.get(period)

    if period == "all":
        rows = (await session.execute(text("""
            SELECT user_id, username, first_name, referrals_count as cnt
            FROM users
            WHERE referrals_count > 0
            ORDER BY referrals_count DESC
            LIMIT 10
        """))).fetchall()

        user_rank = (await session.execute(text("""
            SELECT COUNT(*) + 1 FROM users WHERE referrals_count > :cnt
        """), {"cnt": db_user.referrals_count})).scalar()
        user_cnt = db_user.referrals_count
    else:
        start = datetime.utcnow() - timedelta(days=days)
        rows = (await session.execute(text("""
            SELECT u.user_id, u.username, u.first_name, COUNT(r.user_id) as cnt
            FROM users u
            JOIN users r ON r.referrer_id = u.user_id
            WHERE r.created_at >= :start
            GROUP BY u.user_id
            ORDER BY cnt DESC
            LIMIT 10
        """), {"start": start})).fetchall()

        user_cnt = (await session.execute(text("""
            SELECT COUNT(*) FROM users
            WHERE referrer_id = :uid AND created_at >= :start
        """), {"uid": db_user.user_id, "start": start})).scalar() or 0

        user_rank = (await session.execute(text("""
            SELECT COUNT(*) + 1 FROM (
                SELECT referrer_id, COUNT(*) as cnt
                FROM users
                WHERE created_at >= :start AND referrer_id IS NOT NULL
                GROUP BY referrer_id
            ) sub WHERE sub.cnt > :my_cnt
        """), {"start": start, "my_cnt": user_cnt})).scalar()

    lines = [f"👥 <b>Топ по рефералам — {period_label}</b>\n"]

    if not rows:
        lines.append("Пока нет данных за этот период.")
    else:
        for pos, row in enumerate(rows, start=1):
            uid, username, first_name, cnt = row
            display = f"@{username}" if username else (first_name or f"ID {uid}")
            medal = _format_pos(pos)
            lines.append(f"{medal} {display} — <b>{cnt}</b> реф.")

    u_display = f"@{db_user.username}" if db_user.username else db_user.first_name
    lines.append(
        f"\n📍 <b>Ваше место:</b> #{user_rank}\n"
        f"👤 {u_display} — <b>{user_cnt}</b> реф. за {period_label}"
    )

    await safe_edit(callback, "\n".join(lines), top_result_kb("refs"))
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("top:stars:"))
async def cb_top_stars(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    period = callback.data.split(":")[2]
    period_label = PERIOD_LABELS.get(period, period)

    rows = (await session.execute(text("""
        SELECT user_id, username, first_name, stars_balance as cnt
        FROM users
        WHERE stars_balance > 0
        ORDER BY stars_balance DESC
        LIMIT 10
    """))).fetchall()

    user_rank = (await session.execute(text("""
        SELECT COUNT(*) + 1 FROM users WHERE stars_balance > :bal
    """), {"bal": db_user.stars_balance})).scalar()

    lines = [f"⭐ <b>Топ по звёздам — {period_label}</b>\n"]

    if not rows:
        lines.append("Пока нет данных.")
    else:
        for pos, row in enumerate(rows, start=1):
            uid, username, first_name, bal = row
            display = f"@{username}" if username else (first_name or f"ID {uid}")
            medal = _format_pos(pos)
            lines.append(f"{medal} {display} — <b>{bal:.0f} ⭐</b>")

    u_display = f"@{db_user.username}" if db_user.username else db_user.first_name
    lines.append(
        f"\n📍 <b>Ваше место:</b> #{user_rank}\n"
        f"👤 {u_display} — <b>{db_user.stars_balance:.0f} ⭐</b>"
    )

    await safe_edit(callback, "\n".join(lines), top_result_kb("stars"))
    await callback.answer()
