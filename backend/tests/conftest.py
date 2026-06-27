import asyncio
from typing import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_ROLES = [
    ("student", "Student"),
    ("pharmacist", "Pharmacist"),
    ("educator", "Educator"),
    ("content_reviewer", "Content Reviewer"),
    ("institution_admin", "Institution Administrator"),
    ("platform_admin", "Platform Administrator"),
]

# Governance permissions — name, display_name, resource, action
_PERMISSIONS = [
    ("content.import", "Import Content", "content", "import"),
    ("content.review", "Review Content", "content", "review"),
    ("content.approve", "Approve Content", "content", "approve"),
    ("content.publish", "Publish Content", "content", "publish"),
    ("content.unpublish", "Unpublish Content", "content", "unpublish"),
    ("content.version.create", "Create Content Version", "content", "version.create"),
    ("content.rollback", "Rollback Content Version", "content", "rollback"),
    ("evidence.manage", "Manage Evidence Sources", "evidence", "manage"),
    ("analytics.view", "View Analytics", "analytics", "view"),
    ("analytics.view_org", "View Organization Analytics", "analytics", "view_org"),
]

# Which permissions each role receives
_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "educator": [
        "content.import", "content.review", "content.version.create", "analytics.view",
    ],
    "content_reviewer": [
        "content.review", "content.approve", "content.version.create",
        "evidence.manage", "analytics.view",
    ],
    "institution_admin": [
        "content.import", "content.review", "content.approve",
        "content.publish", "content.unpublish", "content.version.create",
        "content.rollback", "evidence.manage", "analytics.view", "analytics.view_org",
    ],
    "platform_admin": [
        "content.import", "content.review", "content.approve",
        "content.publish", "content.unpublish", "content.version.create",
        "content.rollback", "evidence.manage", "analytics.view", "analytics.view_org",
    ],
}


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Session-scoped engine for unit tests that don't write to the DB."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def fresh_engine():
    """Per-test engine: isolated in-memory DB with tables + seeded roles and permissions."""
    from app.models.identity import Permission, Role, RolePermission

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as s:
        # Seed roles
        for name, display_name in _ROLES:
            s.add(Role(name=name, display_name=display_name, is_system_role=True))
        await s.flush()

        # Seed permissions
        for perm_name, display_name, resource, action in _PERMISSIONS:
            s.add(Permission(name=perm_name, display_name=display_name, resource=resource, action=action))
        await s.flush()

        # Assign permissions to roles
        for role_name, perm_names in _ROLE_PERMISSIONS.items():
            role_result = await s.execute(select(Role).where(Role.name == role_name))
            role = role_result.scalar_one()
            for perm_name in perm_names:
                perm_result = await s.execute(select(Permission).where(Permission.name == perm_name))
                perm = perm_result.scalar_one()
                s.add(RolePermission(role_id=role.id, permission_id=perm.id))

        await s.commit()

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncIterator[AsyncSession]:
    """Per-test session on the session-scoped engine (for unit tests)."""
    TestSessionLocal = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(fresh_engine) -> AsyncIterator[AsyncClient]:
    """Per-test HTTP client backed by a fully isolated in-memory database."""
    SessionLocal = async_sessionmaker(
        bind=fresh_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
