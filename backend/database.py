from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite+aiosqlite:///./documents.db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def _ensure_sqlite_document_columns(conn):
    """create_all does not ALTER existing tables; add columns from newer models."""
    result = await conn.execute(text("PRAGMA table_info(documents)"))
    rows = result.fetchall()
    if not rows:
        return
    col_names = {row[1] for row in rows}
    if "saved_analysis_json" not in col_names:
        await conn.execute(text("ALTER TABLE documents ADD COLUMN saved_analysis_json TEXT"))
    if "saved_changes_json" not in col_names:
        await conn.execute(text("ALTER TABLE documents ADD COLUMN saved_changes_json TEXT"))


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_sqlite_document_columns(conn)
