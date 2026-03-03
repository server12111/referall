from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from database.models import ButtonContent, BotSettings

DATABASE_URL = "sqlite+aiosqlite:///./database.db"

engine = create_async_engine(DATABASE_URL, echo=False)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_setting(session: AsyncSession, key: str, default: str = "") -> str:
    row = await session.get(BotSettings, key)
    return row.value if row else default


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(BotSettings, key)
    if row:
        row.value = value
    else:
        session.add(BotSettings(key=key, value=value))
    await session.commit()


async def get_button_content(session: AsyncSession, key: str) -> ButtonContent | None:
    return await session.get(ButtonContent, key)


async def set_button_photo(session: AsyncSession, key: str, file_id: str | None) -> None:
    row = await session.get(ButtonContent, key)
    if row:
        row.photo_file_id = file_id
    else:
        session.add(ButtonContent(key=key, photo_file_id=file_id))
    await session.commit()


async def set_button_text(session: AsyncSession, key: str, text: str | None) -> None:
    row = await session.get(ButtonContent, key)
    if row:
        row.text = text
    else:
        session.add(ButtonContent(key=key, text=text))
    await session.commit()
