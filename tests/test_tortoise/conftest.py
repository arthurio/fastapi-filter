from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from tortoise import Model, fields, Tortoise, generate_config
from tortoise.contrib.fastapi import RegisterTortoise

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
async def init(database_url):
    # Here we create a SQLite DB using file "db.sqlite3"
    #  also specify the app name of "models"
    #  which contain models from "app.models"
    await Tortoise.init(
        db_url=database_url,
        modules={'models': ['app.models']}
    )
    # Generate the schema
    await Tortoise.generate_schemas()




@pytest.fixture(scope="session")
def User(Address, FavoriteSport, Sport):
    class User(Model):  # type: ignore[misc, valid-type]
        id = fields.IntField(primary_key=True)
        created_at = fields.DatetimeField(null=True, auto_now_add=True)
        updated_at = fields.DatetimeField(null=True, auto_now=True)
        name = fields.CharField(max_length=255)
        age = fields.IntField(null=False)
        address_id = fields.ForeignKeyField('models.Address', related_name="users")

    return User


@pytest.fixture(scope="session")
def Address():
    class Address(Model):  # type: ignore[misc, valid-type]
        id = fields.IntField(primary_key=True)
        street = fields.CharField(128, null=False)
        city = fields.CharField(128, null=False)
        country = fields.CharField(128, null=False)

    return Address


@pytest.fixture(scope="session")
def Sport():
    class Sport(Model):  # type: ignore[misc, valid-type]

        id = fields.IntField(primary_key=True)
        name = fields.CharField(128, null=False)
        is_individual = fields.BooleanField(null=False)

    return Sport


@pytest.fixture(scope="session")
def FavoriteSport():
    class FavoriteSport(Model):  # type: ignore[misc, valid-type]
        user_id = fields.ForeignKeyField('models.User')
        sport_id = fields.ForeignKeyField('models.Sport')

    return FavoriteSport


@pytest_asyncio.fixture(scope="function")
async def users(sports, User, Address):
    user_instances = [
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
    await User.bulk_create(user_instances)
    yield user_instances


@pytest_asyncio.fixture(scope="function")
async def sports(Sport):
    sport_instances = [
        Sport(
            name="Ice Hockey",
            is_individual=False,
        ),
        Sport(
            name="Tennis",
            is_individual=True,
        ),
    ]
    await Sport.bulk_create(sport_instances)
    yield sports


@pytest_asyncio.fixture(scope="function")
async def favorite_sports(sports, users, FavoriteSport):
    favorite_sport_instances = [
        FavoriteSport(
            user_id=users[0].id,
            sport_id=sports[0].id,
        ),
        FavoriteSport(
            user_id=users[0].id,
            sport_id=sports[1].id,
        ),
        FavoriteSport(
            user_id=users[1].id,
            sport_id=sports[0].id,
        ),
        FavoriteSport(
            user_id=users[2].id,
            sport_id=sports[1].id,
        ),
    ]
    await FavoriteSport.bulk_create(favorite_sport_instances)
    yield favorite_sport_instances


@pytest.fixture(scope="package")
def AddressOut():
    class AddressOut(BaseModel):
        model_config = ConfigDict(from_attributes=True)

        id: int
        street: Optional[str]
        city: str
        country: str

    return AddressOut


@pytest.fixture(scope="package")
def UserOut(AddressOut, SportOut):
    class UserOut(BaseModel):
        model_config = ConfigDict(from_attributes=True)

        id: int
        created_at: datetime
        updated_at: datetime
        name: Optional[str]
        age: int
        address: Optional[AddressOut]  # type: ignore[valid-type]
        favorite_sports: Optional[list[SportOut]]  # type: ignore[valid-type]

    return UserOut


@pytest.fixture(scope="package")
def SportOut():
    class SportOut(BaseModel):
        model_config = ConfigDict(from_attributes=True)

        id: int
        name: str
        is_individual: bool

    return SportOut


@pytest.fixture(scope="package")
def Filter():
    yield SQLAlchemyFilter


@pytest.fixture(scope="package")
def AddressFilter(Address, Filter):
    class AddressFilter(Filter):  # type: ignore[misc, valid-type]
        street__isnull: Optional[bool] = None
        city: Optional[str] = None
        city__in: Optional[list[str]] = None
        country__not_in: Optional[list[str]] = None

        class Constants(Filter.Constants):  # type: ignore[name-defined]
            model = Address

    yield AddressFilter


@pytest.fixture(scope="package")
def UserFilter(User, Filter, AddressFilter):
    class UserFilter(Filter):  # type: ignore[misc, valid-type]
        name: Optional[str] = None
        name__neq: Optional[str] = None
        name__like: Optional[str] = None
        name__ilike: Optional[str] = None
        name__in: Optional[list[str]] = None
        name__not: Optional[str] = None
        name__not_in: Optional[list[str]] = None
        name__isnull: Optional[bool] = None
        age: Optional[int] = None
        age__lt: Optional[int] = None
        age__lte: Optional[int] = None
        age__gt: Optional[int] = None
        age__gte: Optional[int] = None
        age__in: Optional[list[int]] = None
        address: Optional[AddressFilter] = FilterDepends(  # type: ignore[valid-type]
            with_prefix("address", AddressFilter), by_alias=True
        )
        address_id__isnull: Optional[bool] = None
        search: Optional[str] = None

        class Constants(Filter.Constants):  # type: ignore[name-defined]
            model = User
            search_model_fields = ["name"]
            search_field_name = "search"

    yield UserFilter


@pytest.fixture(scope="package")
def UserFilterByAlias(UserFilter, AddressFilter):
    class UserFilterByAlias(UserFilter):  # type: ignore[misc, valid-type]
        address: Optional[AddressFilter] = FilterDepends(  # type: ignore[valid-type]
            with_prefix("address", AddressFilter), by_alias=True
        )

    yield UserFilterByAlias


@pytest.fixture(scope="package")
def SportFilter(Sport, Filter):
    class SportFilter(Filter):  # type: ignore[misc, valid-type]
        name: Optional[str] = Field(Query(description="Name of the sport", default=None))
        is_individual: bool
        bogus_filter: Optional[str] = None

        class Constants(Filter.Constants):  # type: ignore[name-defined]
            model = Sport

        @field_validator("bogus_filter")
        def throw_exception(cls, value):
            if value:
                raise ValueError("You can't use this bogus filter")

    yield SportFilter


@pytest.fixture(scope="package")
def app(
    Address,
    FavoriteSport,
    Sport,
    SportFilter,
    SportOut,
    User,
    UserFilter,
    UserFilterByAlias,
    UserFilterCustomOrderBy,
    UserFilterOrderBy,
    UserFilterOrderByWithDefault,
    UserFilterRestrictedOrderBy,
    UserOut,
):
    @asynccontextmanager
    async def lifespan_test(app: FastAPI) -> AsyncGenerator[None, None]:
        config = generate_config(
            os.getenv("TORTOISE_TEST_DB", "sqlite://:memory:"),
            app_modules={"models": ["models"]},
            testing=True,
            connection_label="models",
        )
        async with RegisterTortoise(
                app=app,
                config=config,
                generate_schemas=True,
                add_exception_handlers=True,
                _create_db=True,
        ):
            # db connected
            yield
            # app teardown
        # db connections closed
        await Tortoise._drop_databases()


    app = FastAPI(lifespan=lifespan_test)

    @app.get("/users", response_model=list[UserOut])  # type: ignore[valid-type]
    async def get_users(
        user_filter: UserFilter = FilterDepends(UserFilter),  # type: ignore[valid-type]
    ):
        return await user_filter.filter(User.all().select_related('address'))  # type: ignore[attr-defined]

    @app.get("/users-by-alias", response_model=list[UserOut])  # type: ignore[valid-type]
    async def get_users_by_alias(
        user_filter: UserFilter = FilterDepends(UserFilterByAlias, by_alias=True),  # type: ignore[valid-type]
    ):
        return await user_filter.filter(User.all().select_related('address'))  # type: ignore[attr-defined]

    @app.get("/users_with_order_by", response_model=list[UserOut])  # type: ignore[valid-type]
    async def get_users_with_order_by(
        user_filter: UserFilterOrderBy = FilterDepends(UserFilterOrderBy),  # type: ignore[valid-type]
    ):
        query = user_filter.sort(User.all().select_related('address'))  # type: ignore[attr-defined]
        return await user_filter.filter(query)  # type: ignore[attr-defined]

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
        return await sport_filter.filter(Sport.all())  # type: ignore[attr-defined]

    yield app
