from datetime import datetime
from typing import AsyncIterator, Optional

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


@pytest.fixture(scope="session")
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


@pytest.fixture(scope="session")
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
        street__isnull: Optional[bool]
        city: Optional[str]
        city__in: Optional[list[str]]
        country__not_in: Optional[list[str]]

        class Constants(Filter.Constants):
            model = Address

    yield AddressFilter


@pytest.fixture(scope="package")
def UserFilter(User, Filter, AddressFilter):
    class UserFilter(Filter):
        name: Optional[str]
        name__in: Optional[list[str]]
        name__not: Optional[str]
        name__not_in: Optional[list[str]]
        name__isnull: Optional[bool]
        age: Optional[int]
        age__lt: Optional[int]
        age__lte: Optional[int]
        age__gt: Optional[int]
        age__gte: Optional[int]
        age__in: Optional[list[int]]
        address: Optional[AddressFilter] = FilterDepends(with_prefix("address", AddressFilter))
        address_id__isnull: Optional[bool]

        class Constants(Filter.Constants):
            model = User

    yield UserFilter


@pytest.fixture(scope="package")
def app(
    Address,
    SessionLocal,
    User,
    UserFilter,
    UserFilterCustomOrderBy,
    UserFilterOrderBy,
    UserFilterOrderByWithDefault,
    UserFilterRestrictedOrderBy,
    UserOut,
):
    app = FastAPI()

    async def get_db() -> AsyncIterator[AsyncSession]:
        async with SessionLocal() as session:
            yield session

    @app.get("/users", response_model=list[UserOut])
    async def get_users(
        user_filter: UserFilter = FilterDepends(UserFilter),
        db: AsyncSession = Depends(get_db),
    ):
        query = user_filter.filter(select(User).outerjoin(Address))  # type: ignore[attr-defined]
        result = await db.execute(query)
        return result.scalars().all()

    @app.get("/users_with_order_by", response_model=list[UserOut])
    async def get_users_with_order_by(
        user_filter: UserFilterOrderBy = FilterDepends(UserFilterOrderBy),
        db: AsyncSession = Depends(get_db),
    ):
        query = user_filter.sort(select(User).outerjoin(Address))  # type: ignore[attr-defined]
        query = user_filter.filter(query)  # type: ignore[attr-defined]
        result = await db.execute(query)
        return result.scalars().all()

    @app.get("/users_with_no_order_by", response_model=list[UserOut])
    async def get_users_with_no_order_by(
        user_filter: UserFilter = FilterDepends(UserFilter),
    ):
        return await get_users_with_order_by(user_filter)

    @app.get("/users_with_default_order_by", response_model=list[UserOut])
    async def get_users_with_default_order_by(
        user_filter: UserFilterOrderByWithDefault = FilterDepends(UserFilterOrderByWithDefault),
        db: AsyncSession = Depends(get_db),
    ):
        return await get_users_with_order_by(user_filter, db)

    @app.get("/users_with_restricted_order_by", response_model=list[UserOut])
    async def get_users_with_restricted_order_by(
        user_filter: UserFilterRestrictedOrderBy = FilterDepends(UserFilterRestrictedOrderBy),
        db: AsyncSession = Depends(get_db),
    ):
        return await get_users_with_order_by(user_filter, db)

    @app.get("/users_with_custom_order_by", response_model=list[UserOut])
    async def get_users_with_custom_order_by(
        user_filter: UserFilterCustomOrderBy = FilterDepends(UserFilterCustomOrderBy),
        db: AsyncSession = Depends(get_db),
    ):
        return await get_users_with_order_by(user_filter, db)

    yield app
