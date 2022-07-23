from datetime import datetime
from typing import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from fastapi_filter import FilterDepends, with_prefix
from fastapi_filter.contrib.sqlalchemy import Filter as SQLAlchemyFilter


@pytest.fixture(scope="session")
def sqlite_file_path(tmp_path_factory):
    file_path = tmp_path_factory.mktemp("data") / "fastapi_filter_test.sqlite"
    yield file_path


@pytest.fixture(scope="session")
def database_url(sqlite_file_path) -> str:
    return f"sqlite+aiosqlite:///{sqlite_file_path}"


@pytest.fixture(scope="session")
def engine(database_url):
    return create_async_engine(database_url)


@pytest.fixture(scope="session")
def SessionLocal(engine):
    return sessionmaker(autoflush=True, bind=engine, class_=AsyncSession)


@pytest_asyncio.fixture(scope="function")
async def session(engine, SessionLocal, Base):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="session")
def Base(engine):
    return declarative_base(bind=engine)


@pytest.fixture(scope="package")
def User(Base, Address):
    class User(Base):
        __tablename__ = "users"

        id = Column(Integer, primary_key=True, autoincrement=True)
        created_at = Column(DateTime, default=datetime.now, nullable=False)
        updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
        name = Column(String)
        age = Column(Integer, nullable=False)
        address_id = Column(Integer, ForeignKey("addresses.id"))
        address: Address = relationship(Address, backref="users", lazy="joined")

    return User


@pytest.fixture(scope="package")
def Address(Base):
    class Address(Base):
        __tablename__ = "addresses"

        id = Column(Integer, primary_key=True, autoincrement=True)
        street = Column(String, nullable=True)
        city = Column(String, nullable=False)
        country = Column(String, nullable=False)

    return Address


@pytest_asyncio.fixture(scope="function")
async def users(session, User, Address):
    session.add_all(
        [
            User(
                name=None,
                age=21,
                created_at=datetime(2021, 12, 1),
            ),
            User(
                name="Mr Praline",
                age=33,
                created_at=datetime(2021, 12, 1),
                address=Address(street="22 rue Bellier", city="Nantes", country="France"),
            ),
            User(
                name="The colonel",
                age=90,
                created_at=datetime(2021, 12, 2),
                address=Address(street="Wrench", city="Bathroom", country="Clue"),
            ),
            User(
                name="Mr Creosote",
                age=21,
                created_at=datetime(2021, 12, 3),
                address=Address(city="Nantes", country="France"),
            ),
            User(
                name="Rabbit of Caerbannog",
                age=1,
                created_at=datetime(2021, 12, 4),
                address=Address(street="1234 street", city="San Francisco", country="United States"),
            ),
            User(
                name="Gumbys",
                age=50,
                created_at=datetime(2021, 12, 4),
                address=Address(street="4567 avenue", city="Denver", country="United States"),
            ),
        ]
    )
    await session.commit()


@pytest.fixture(scope="package")
def Filter():
    yield SQLAlchemyFilter


@pytest.fixture(scope="package")
def AddressFilter(Address, Filter):
    class AddressFilter(Filter):
        street__isnull: bool | None
        city: str | None
        city__in: list[str] | None
        country__not_in: list[str] | None

        class Constants(Filter.Constants):
            model = Address

    yield AddressFilter


@pytest.fixture(scope="package")
def UserFilter(User, Filter, AddressFilter):
    class UserFilter(Filter):
        name: str | None
        name__in: list[str] | None
        name__not: str | None
        name__not_in: list[str] | None
        name__isnull: bool | None
        age: int | None
        age__lt: int | None
        age__lte: int | None
        age__gt: int | None
        age__gte: int | None
        age__in: list[int] | None
        address: AddressFilter | None = FilterDepends(with_prefix("address", AddressFilter))
        address_id__isnull: bool | None

        class Constants(Filter.Constants):
            model = User

    yield UserFilter


@pytest.fixture(scope="package")
def app(SessionLocal, Address, User, UserOut, UserFilterOrderBy, UserFilterOrderByWithDefault):
    app = FastAPI()

    async def get_db() -> AsyncIterator[AsyncSession]:
        async with SessionLocal() as session:
            yield session

    @app.get("/users", response_model=list[UserOut])
    async def get_users(
        user_filter: UserFilterOrderBy = FilterDepends(UserFilterOrderBy), db: AsyncSession = Depends(get_db)
    ):
        query = user_filter.filter(select(User).outerjoin(Address))  # type: ignore[attr-defined]
        query = user_filter.sort(query)  # type: ignore[attr-defined]
        result = await db.execute(query)
        return result.scalars().all()

    @app.get("/users_with_default", response_model=list[UserOut])
    async def get_users_with_default(
        user_filter: UserFilterOrderByWithDefault = FilterDepends(UserFilterOrderByWithDefault),
        db: AsyncSession = Depends(get_db),
    ):
        query = user_filter.filter(select(User).outerjoin(Address))  # type: ignore[attr-defined]
        query = user_filter.sort(query)  # type: ignore[attr-defined]
        result = await db.execute(query)
        return result.scalars().all()

    yield app
