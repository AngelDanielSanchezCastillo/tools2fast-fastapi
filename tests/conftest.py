import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# Import testing dummy models to ensure they are picked up in metadata
from tests.test_revision_service import DocumentHeader, DocumentItem

from sqlalchemy.pool import StaticPool

@pytest_asyncio.fixture
async def session():
    """Provides an active async DB session for tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
        
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
