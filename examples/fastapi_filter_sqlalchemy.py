from typing import Any, AsyncIterator, Optional

import uvicorn
from faker import Faker
from fastapi import Depends, FastAPI, Query
from pydantic import BaseModel, Field
from sqlalchemy import Column, ForeignKey, Integer, String, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from fastapi_filter import FilterDepends, with_prefix
from fastapi_filter.contrib.sqlalchemy import Filter


@event.listens_for(Engine, "connect")
def _set_sqlite_case_sensitive_pragma(dbapi_con, connection_record):
    cursor = dbapi_con.cursor()
    cursor.execute("PRAGMA case_sensitive_like=ON;")
    cursor.close()


engine = create_async_engine("sqlite+aiosqlite:///fastapi_filter.sqlite")

async_session = sessionmaker(engine, class_=AsyncSession)

Base = declarative_base()

fake = Faker()


class Address(Base):
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    street = Column(String, nullable=False)
    city = Column(String, nullable=False)
    country = Column(String, nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    address_id = Column(Integer, ForeignKey("addresses.id"), nullable=True)
    address: Address = relationship(Address, backref="users", lazy="joined")


class AddressOut(BaseModel):
    id: int
    street: str
    city: str
    country: str

    class Config:
        orm_mode = True


class UserIn(BaseModel):
    name: str
    email: str
    age: int


class UserOut(UserIn):
    id: int
    address: Optional[AddressOut]

    class Config:
        orm_mode = True


class AddressFilter(Filter):
    street: Optional[str]
    country: Optional[str]
    city: Optional[str]
    city__in: Optional[list[str]]
    custom_order_by: Optional[list[str]]

    class Constants(Filter.Constants):
        model = Address
        ordering_field_name = "custom_order_by"


class UserFilter(Filter):
    name: Optional[str]
    name__ilike: Optional[str]
    name__like: Optional[str]
    name__neq: Optional[str]
    address: Optional[AddressFilter] = FilterDepends(with_prefix("address", AddressFilter))
    age__lt: Optional[int]
    age__gte: int = Field(Query(description="this is a nice description"))
    """Required field with a custom description.

    See: https://github.com/tiangolo/fastapi/issues/4700 for why we need to wrap `Query` in `Field`.
    """
    order_by: list[str] = ["age"]

    class Constants(Filter.Constants):
        model = User


app = FastAPI()


@app.on_event("startup")
async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        for _ in range(100):
            address = Address(street=fake.street_address(), city=fake.city(), country=fake.country())
            user = User(name=fake.name(), email=fake.email(), age=fake.random_int(min=5, max=120), address=address)

            session.add_all([address, user])
        await session.commit()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session


@app.get("/users", response_model=list[UserOut])
async def get_users(
    user_filter: UserFilter = FilterDepends(UserFilter),
    db: AsyncSession = Depends(get_db),
) -> Any:
    query = select(User).outerjoin(Address)
    query = user_filter.filter(query)
    query = user_filter.sort(query)
    result = await db.execute(query)
    return result.scalars().all()


@app.get("/addresses", response_model=list[AddressOut])
async def get_addresses(
    address_filter: AddressFilter = FilterDepends(with_prefix("my_prefix", AddressFilter), by_alias=True),
    db: AsyncSession = Depends(get_db),
) -> Any:
    query = select(Address)
    query = address_filter.filter(query)
    query = address_filter.sort(query)
    result = await db.execute(query)
    return result.scalars().all()


if __name__ == "__main__":
    uvicorn.run("fastapi_filter_sqlalchemy:app", reload=True)
