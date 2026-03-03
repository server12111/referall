from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import User
from handlers.button_helper import safe_edit
from keyboards.main import back_to_menu_kb

router = Router()


class SearchStates(StatesGroup):
    username = State()


@router.callback_query(lambda c: c.data == "menu:search")
async def cb_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchStates.username)
    await safe_edit(
        callback,
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Введи username (без @) — и я скажу, есть ли этот человек в боте:",
        back_to_menu_kb(),
    )
    await callback.answer()


@router.message(SearchStates.username)
async def msg_search_username(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await state.clear()
    username = message.text.strip().lstrip("@")

    if not username:
        await message.answer("❌ Введи корректный username.", reply_markup=back_to_menu_kb())
        return

    user = (await session.execute(
        select(User).where(User.username == username)
    )).scalar_one_or_none()

    if user:
        await message.answer(
            f"✨ <b>Пользователь найден в боте!</b>\n\n"
            f"👤 Имя: <b>{user.first_name}</b>\n"
            f"🔗 Username: @{user.username}\n"
            f"🆔 ID: <code>{user.user_id}</code>\n\n"
            f"✅ Этот пользователь зарегистрирован в нашем боте.",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
    else:
        await message.answer(
            f"🔍 <b>Поиск завершён</b>\n\n"
            f"😔 Пользователь <b>@{username}</b> не найден.\n\n"
            f"Возможно, он ещё не зарегистрировался в боте.\n"
            f"Пригласи его по реферальной ссылке! 🎁",
            parse_mode="HTML",
            reply_markup=back_to_menu_kb(),
        )
