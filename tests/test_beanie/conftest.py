import asyncio
from collections.abc import AsyncGenerator, Generator
from datetime import datetime
from typing import Optional

import pytest
import pytest_asyncio
from beanie import Document, Link, PydanticObjectId, init_beanie
from beanie.odm.fields import WriteRules
from fastapi import FastAPI, Query
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from fastapi_filter import FilterDepends, with_prefix
from fastapi_filter.contrib.beanie import Filter as MongoFilter


class Address(Document):
    street: Optional[str] = None
    city: str
    country: str


class Sport(Document):
    name: str
    is_individual: bool


class User(Document):
    created_at: datetime
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    age: int
    address: Optional[Link[Address]] = None
    favorite_sports: Optional[list[Link[Sport]]] = []


@pytest.fixture(scope="session")
def database_url() -> str:
    return "mongodb://127.0.0.1"


@pytest_asyncio.fixture(scope="session")
async def db_connect(database_url):
    client: AsyncIOMotorClient = AsyncIOMotorClient(database_url)
    # https://github.com/tiangolo/fastapi/issues/3855#issuecomment-1013148113
    client.get_io_loop = asyncio.get_event_loop  # type: ignore[method-assign]
    db = client.test_db
    await init_beanie(database=db, document_models=[Address, Sport, User])
    yield db
    await client.drop_database("test_db")


@pytest.fixture(scope="session", name="User")
def user_model_fixture(db_connect) -> type[User]:
    return User


@pytest.fixture(scope="session", name="Address")
def address_model_fixture(db_connect) -> type[Address]:
    return Address


@pytest.fixture(scope="session", name="Sport")
def sport_model_fixture(db_connect) -> type[Sport]:
    return Sport


@pytest_asyncio.fixture(scope="session")
async def sports(Sport: Document) -> AsyncGenerator[list[Sport], None]:  # noqa: N803
    sports = [
        await Sport(name="Ice Hockey", is_individual=False).save(),
        await Sport(name="Tennis", is_individual=True).save(),
    ]

    yield sports  # noqa: PT022


@pytest_asyncio.fixture(scope="session")
async def users(
    User: Document,  # noqa: N803
    Address: Document,  # noqa: N803
    sports: list[Sport],
) -> AsyncGenerator[list[User], None]:
    users = [
        await User(
            name=None,
            age=21,
            created_at=datetime(2021, 12, 1),
            favorite_sports=sports,
        ).save(link_rule=WriteRules.WRITE),
        await User(
            name="Mr Praline",
            age=33,
            created_at=datetime(2021, 12, 1),
            address=Address(street="22 rue Bellier", city="Nantes", country="France"),
            favorite_sports=[sports[0]],
        ).save(link_rule=WriteRules.WRITE),
        await User(
            name="The colonel",
            age=90,
            created_at=datetime(2021, 12, 2),
            address=Address(street="Wrench", city="Bathroom", country="Clue"),
            favorite_sports=[sports[1]],
        ).save(link_rule=WriteRules.WRITE),
        await User(
            name="Mr Creosote",
            age=21,
            created_at=datetime(2021, 12, 3),
            address=Address(city="Nantes", country="France"),
        ).save(link_rule=WriteRules.WRITE),
        await User(
            name="Rabbit of Caerbannog",
            age=1,
            created_at=datetime(2021, 12, 4),
            address=Address(street="1234 street", city="San Francisco", country="United States"),
        ).save(link_rule=WriteRules.WRITE),
        await User(
            name="Gumbys",
            age=50,
            created_at=datetime(2021, 12, 4),
            address=Address(street="4567 avenue", city="Denver", country="United States"),
        ).save(link_rule=WriteRules.WRITE),
    ]
    yield users  # noqa: PT022


@pytest.fixture(scope="package")
def AddressFilter(Address: Document, Filter: MongoFilter):
    class AddressFilter(Filter):  # type: ignore[misc, valid-type]
        street__isnull: Optional[bool] = None
        country: Optional[str] = None
        city: Optional[str] = None
        city__in: Optional[list[str]] = None
        country__nin: Optional[list[str]] = None

        class Constants(MongoFilter.Constants):  # type: ignore[name-defined]
            model = Address

    yield AddressFilter


@pytest.fixture(scope="package")
def UserFilter(User, Filter, AddressFilter):
    class UserFilter(Filter):  # type: ignore[misc, valid-type]
        name: Optional[str] = None
        name__in: Optional[list[str]] = None
        name__nin: Optional[list[str]] = None
        name__ne: Optional[str] = None
        name__isnull: Optional[bool] = None
        age: Optional[int] = None
        age__lt: Optional[int] = None
        age__lte: Optional[int] = None
        age__gt: Optional[int] = None
        age__gte: Optional[int] = None
        age__in: Optional[list[int]] = None
        address: Optional[AddressFilter] = FilterDepends(  # type: ignore[valid-type]
            with_prefix("address", AddressFilter),
        )
        search: Optional[str] = None

        class Constants(MongoFilter.Constants):  # type: ignore[name-defined]
            model = User
            search_model_fields = ["name", "email"]  # noqa: RUF012
            search_field_name = "search"
            ordering_field_name = "order_by"

    yield UserFilter


@pytest.fixture(scope="package")
def UserFilterByAlias(UserFilter, AddressFilter):
    class UserFilterByAlias(UserFilter):  # type: ignore[misc, valid-type]
        address: Optional[AddressFilter] = FilterDepends(  # type: ignore[valid-type]
            with_prefix("address", AddressFilter),
            by_alias=True,
        )

    yield UserFilterByAlias


@pytest.fixture(scope="package")
def SportFilter(Sport, Filter):
    class SportFilter(MongoFilter):  # type: ignore[misc, valid-type]
        name: Optional[str] = Field(Query(description="Name of the sport", default=None))
        is_individual: bool
        bogus_filter: Optional[str] = None

        class Constants(MongoFilter.Constants):  # type: ignore [name-defined]
            model = Sport

        @field_validator("bogus_filter")
        def throw_exception(cls, value):
            if value:
                raise ValueError("You can't use this bogus filter")

    yield SportFilter


@pytest.fixture(scope="package")
def AddressOut():
    class AddressOut(BaseModel):
        model_config = ConfigDict(from_attributes=True)

        id: Optional[PydanticObjectId] = Field(default=None, description="MongoDB document ObjectID")
        street: Optional[str] = None
        city: str
        country: str

    yield AddressOut


@pytest.fixture(scope="package")
def UserOut(AddressOut):
    class UserOut(BaseModel):
        model_config = ConfigDict(from_attributes=True)

        id: Optional[PydanticObjectId] = Field(default=None, description="MongoDB document ObjectID")
        created_at: datetime
        name: Optional[str] = None
        age: int
        address: Optional[AddressOut] = None  # type: ignore[valid-type]

    yield UserOut


@pytest.fixture(scope="package")
def SportOut():
    class SportOut(BaseModel):
        model_config = ConfigDict(from_attributes=True)

        id: Optional[PydanticObjectId] = Field(default=None, description="MongoDB document ObjectID")
        name: str
        is_individual: bool

    yield SportOut


@pytest.fixture(scope="function", autouse=True)
def clear_database(User: Document):
    User.find_all().delete()
    yield
    User.find_all().delete()


@pytest.fixture(scope="package")
def Filter():
    yield MongoFilter


@pytest.fixture(scope="package")
def app(
    Address: Document,
    User: Document,
    SportFilter,
    SportOut: BaseModel,
    Sport: Document,
    UserFilter,
    UserFilterByAlias,
    UserFilterCustomOrderBy,
    UserFilterOrderBy,
    UserFilterOrderByWithDefault,
    UserFilterRestrictedOrderBy,
    UserOut: BaseModel,
) -> Generator[FastAPI, None, None]:
    app = FastAPI()

    @app.get("/users", response_model=list[UserOut])  # type: ignore[valid-type]
    async def get_users(user_filter: UserFilter = FilterDepends(UserFilter)):  # type: ignore[valid-type]
        query = user_filter.filter(User.find({}))  # type: ignore[attr-defined]
        return await query.project(UserOut).to_list()

    @app.get("/users-by-alias", response_model=list[UserOut])  # type: ignore[valid-type]
    async def get_users_by_alias(
        user_filter: UserFilter = FilterDepends(UserFilterByAlias, by_alias=True),  # type: ignore[valid-type]
    ):
        query = user_filter.filter(User.find({}))  # type: ignore[attr-defined]
        return await query.project(UserOut).to_list()

    @app.get("/users_with_order_by", response_model=list[UserOut])  # type: ignore[valid-type]
    async def get_users_with_order_by(
        user_filter: UserFilterOrderBy = FilterDepends(UserFilterOrderBy),  # type: ignore[valid-type]
    ):
        query = user_filter.sort(User.find({}))  # type: ignore[attr-defined]
        query = user_filter.filter(query)  # type: ignore[attr-defined]
        return await query.project(UserOut).to_list()

    @app.get("/users_with_no_order_by", response_model=list[UserOut])  # type: ignore[valid-type]
    async def get_users_with_no_order_by(
        user_filter: UserFilter = FilterDepends(UserFilter),  # type: ignore[valid-type]
    ):
        return await get_users_with_order_by(user_filter)

    @app.get("/users_with_default_order_by", response_model=list[UserOut])  # type: ignore[valid-type]
    async def get_users_with_default_order_by(
        user_filter: UserFilterOrderByWithDefault = FilterDepends(  # type: ignore[valid-type]
            UserFilterOrderByWithDefault
        ),
    ):
        return await get_users_with_order_by(user_filter)

    @app.get("/users_with_restricted_order_by", response_model=list[UserOut])  # type: ignore[valid-type]
    async def get_users_with_restricted_order_by(
        user_filter: UserFilterRestrictedOrderBy = FilterDepends(  # type: ignore[valid-type]
            UserFilterRestrictedOrderBy
        ),
    ):
        return await get_users_with_order_by(user_filter)

    @app.get("/users_with_custom_order_by", response_model=list[UserOut])  # type: ignore[valid-type]
    async def get_users_with_custom_order_by(
        user_filter: UserFilterCustomOrderBy = FilterDepends(UserFilterCustomOrderBy),  # type: ignore[valid-type]
    ):
        return await get_users_with_order_by(user_filter)

    @app.get("/sports", response_model=list[SportOut])  # type: ignore[valid-type]
    async def get_sports(
        sport_filter: SportFilter = FilterDepends(SportFilter),  # type: ignore[valid-type]
    ):
        query = sport_filter.filter(Sport.find({}))  # type: ignore[attr-defined]
        return await query.project(SportOut).to_list()

    yield app  # noqa: PT022
