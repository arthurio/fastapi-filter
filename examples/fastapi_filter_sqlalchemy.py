import logging
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

import click
import uvicorn
from faker import Faker
from fastapi import Depends, FastAPI, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import ForeignKey, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from fastapi_filter import FilterDepends, with_prefix
from fastapi_filter.contrib.sqlalchemy import Filter

logger = logging.getLogger("uvicorn")


@event.listens_for(Engine, "connect")
def _set_sqlite_case_sensitive_pragma(dbapi_con, connection_record):
    cursor = dbapi_con.cursor()
    cursor.execute("PRAGMA case_sensitive_like=ON;")
    cursor.close()


engine = create_async_engine("sqlite+aiosqlite:///fastapi_filter.sqlite")
async_session = async_sessionmaker(engine, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


fake = Faker()


class Address(Base):
    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    street: Mapped[str]
    city: Mapped[str]
    country: Mapped[str]


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str]
    email: Mapped[str]
    age: Mapped[int]
    address_id: Mapped[int | None] = mapped_column(ForeignKey("addresses.id"))
    address: Mapped[Address] = relationship(Address, backref="users", lazy="joined")


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    street: str
    city: str
    country: str


class UserIn(BaseModel):
    name: str
    email: str
    age: int


class UserOut(UserIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    address: AddressOut | None = None


class AddressFilter(Filter):
    street: str | None = None
    country: str | None = None
    city: str | None = None
    city__in: list[str] | None = None
    custom_order_by: list[str] | None = None
    custom_search: str | None = None

    class Constants(Filter.Constants):
        model = Address
        ordering_field_name = "custom_order_by"
        search_field_name = "custom_search"
        search_model_fields = ["street", "country", "city"]


class UserFilter(Filter):
    name: str | None = None
    name__ilike: str | None = None
    name__like: str | None = None
    name__neq: str | None = None
    address: AddressFilter | None = FilterDepends(with_prefix("address", AddressFilter))
    age__lt: int | None = None
    age__gte: int = Field(Query(description="this is a nice description"))
    """Required field with a custom description.

    See: https://github.com/tiangolo/fastapi/issues/4700 for why we need to wrap `Query` in `Field`.
    """
    order_by: list[str] = ["age"]
    search: str | None = None

    class Constants(Filter.Constants):
        model = User
        search_model_fields = ["name"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    message = "Open http://127.0.0.1:8000/docs to start exploring 🎒 🧭 🗺️"
    color_message = "Open " + click.style("http://127.0.0.1:8000/docs", bold=True) + " to start exploring 🎒 🧭 🗺️"
    logger.info(message, extra={"color_message": color_message})

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        for _ in range(100):
            address = Address(street=fake.street_address(), city=fake.city(), country=fake.country())
            user = User(name=fake.name(), email=fake.email(), age=fake.random_int(min=5, max=120), address=address)

            session.add_all([address, user])
        await session.commit()

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


app = FastAPI(lifespan=lifespan)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session


@app.get("/users", response_model=list[UserOut])
async def get_users(
    user_filter: UserFilter = FilterDepends(UserFilter),
    db: AsyncSession = Depends(get_db),
) -> Any:
    query = select(User).join(Address)
    query = user_filter.filter(query)
    query = user_filter.sort(query)
    result = await db.execute(query)
    return result.scalars().all()


@app.get("/users-native", response_model=list[UserOut])
async def get_users_native(
    # For non-nested filters, the native Annotated[Filter, Query()] pattern (FastAPI 0.115+)
    # is simpler and does not require FilterDepends. Use FilterDepends when you need
    # nested filters with with_prefix().
    user_filter: Annotated[UserFilter, Query()],
    db: AsyncSession = Depends(get_db),
) -> Any:
    query = select(User).join(Address)
    query = user_filter.filter(query)
    query = user_filter.sort(query)
    result = await db.execute(query)
    return result.scalars().all()


@app.get("/addresses", response_model=list[AddressOut])
async def get_addresses(
    address_filter: AddressFilter = FilterDepends(with_prefix("my_custom_prefix", AddressFilter), by_alias=True),
    db: AsyncSession = Depends(get_db),
) -> Any:
    query = select(Address)
    query = address_filter.filter(query)
    query = address_filter.sort(query)
    result = await db.execute(query)
    return result.scalars().all()


if __name__ == "__main__":
    uvicorn.run("fastapi_filter_sqlalchemy:app", reload=True)
