from datetime import datetime
from typing import Any, Generator, Optional

import pytest
from bson.objectid import ObjectId
from fastapi import FastAPI
from mongoengine import Document, connect, fields
from pydantic import BaseModel, Field

from fastapi_filter import FilterDepends, with_prefix
from fastapi_filter.contrib.mongoengine import Filter as MongoFilter


@pytest.fixture(scope="session")
def database_url() -> str:
    return "mongodb://127.0.0.1"


@pytest.fixture(scope="session")
def db_connect(database_url):
    connect(host=database_url, uuidRepresentation="standard")


@pytest.fixture(scope="session")
def PydanticObjectId():
    class PydanticObjectId(ObjectId):
        @classmethod
        def __get_validators__(cls) -> Generator:
            yield cls.validate

        @classmethod
        def validate(cls, v: ObjectId) -> str:
            if not ObjectId.is_valid(v):
                raise ValueError("Invalid objectid")
            return str(v)

        @classmethod
        def __modify_schema__(cls, field_schema: dict[str, Any]) -> None:
            field_schema.update(type="string")

    return PydanticObjectId


@pytest.fixture(scope="session")
def User(db_connect, Address):
    class User(Document):
        created_at = fields.DateTimeField()
        name = fields.StringField(null=True)
        email = fields.EmailField()
        age = fields.IntField()
        address = fields.ReferenceField(Address)

    return User


@pytest.fixture(scope="session")
def Address(db_connect):
    class Address(Document):
        street = fields.StringField(null=True)
        city = fields.StringField()
        country = fields.StringField()

    return Address


@pytest.fixture(scope="function")
def users(User, Address):
    User(
        name=None,
        age=21,
        created_at=datetime(2021, 12, 1),
    ).save()
    User(
        name="Mr Praline",
        age=33,
        created_at=datetime(2021, 12, 1),
        address=Address(street="22 rue Bellier", city="Nantes", country="France").save(),
    ).save()
    User(
        name="The colonel",
        age=90,
        created_at=datetime(2021, 12, 2),
        address=Address(street="Wrench", city="Bathroom", country="Clue").save(),
    ).save()
    User(
        name="Mr Creosote",
        age=21,
        created_at=datetime(2021, 12, 3),
        address=Address(city="Nantes", country="France").save(),
    ).save()
    User(
        name="Rabbit of Caerbannog",
        age=1,
        created_at=datetime(2021, 12, 4),
        address=Address(street="1234 street", city="San Francisco", country="United States").save(),
    ).save()
    User(
        name="Gumbys",
        age=50,
        created_at=datetime(2021, 12, 4),
        address=Address(street="4567 avenue", city="Denver", country="United States").save(),
    ).save()


@pytest.fixture(scope="package")
def AddressFilter(Address, Filter):
    class AddressFilter(Filter):
        street__isnull: Optional[bool]
        country: Optional[str]
        city: Optional[str]
        city__in: Optional[list[str]]
        country__nin: Optional[list[str]]

        class Constants(Filter.Constants):
            model = Address

    yield AddressFilter


@pytest.fixture(scope="package")
def UserFilter(User, Filter, AddressFilter):
    class UserFilter(Filter):
        name: Optional[str]
        name__in: Optional[list[str]]
        name__nin: Optional[list[str]]
        name__ne: Optional[str]
        name__isnull: Optional[bool]
        age: Optional[int]
        age__lt: Optional[int]
        age__lte: Optional[int]
        age__gt: Optional[int]
        age__gte: Optional[int]
        age__in: Optional[list[int]]
        address: Optional[AddressFilter] = FilterDepends(with_prefix("address", AddressFilter))

        class Constants(Filter.Constants):
            model = User

    yield UserFilter


@pytest.fixture(scope="package")
def AddressOut(PydanticObjectId):
    class AddressOut(BaseModel):
        id: PydanticObjectId = Field(..., alias="_id")
        street: Optional[str]
        city: str
        country: str

        class Config:
            orm_mode = True

    yield AddressOut


@pytest.fixture(scope="package")
def UserOut(PydanticObjectId, AddressOut):
    class UserOut(BaseModel):
        id: PydanticObjectId = Field(..., alias="_id")
        created_at: datetime
        name: Optional[str]
        age: int
        address: Optional[AddressOut]

        class Config:
            orm_mode = True

    yield UserOut


@pytest.fixture(scope="function", autouse=True)
def clear_database(User):
    User.drop_collection()
    yield
    User.drop_collection()


@pytest.fixture(scope="package")
def Filter():
    yield MongoFilter


@pytest.fixture(scope="package")
def app(
    Address,
    User,
    UserFilter,
    UserFilterCustomOrderBy,
    UserFilterOrderBy,
    UserFilterOrderByWithDefault,
    UserFilterRestrictedOrderBy,
    UserOut,
):
    app = FastAPI()

    @app.get("/users", response_model=list[UserOut])
    async def get_users(user_filter: UserFilter = FilterDepends(UserFilter)):
        query = user_filter.filter(User.objects())  # type: ignore[attr-defined]
        query = query.select_related()
        return [user.to_mongo() | {"address": user.address.to_mongo() if user.address else None} for user in query]

    @app.get("/users_with_order_by", response_model=list[UserOut])
    async def get_users_with_order_by(user_filter: UserFilterOrderBy = FilterDepends(UserFilterOrderBy)):
        query = user_filter.sort(User.objects())  # type: ignore[attr-defined]
        query = user_filter.filter(query)  # type: ignore[attr-defined]
        query = query.select_related()
        return [user.to_mongo() | {"address": user.address.to_mongo() if user.address else None} for user in query]

    @app.get("/users_with_no_order_by", response_model=list[UserOut])
    async def get_users_with_no_order_by(
        user_filter: UserFilter = FilterDepends(UserFilter),
    ):
        return await get_users_with_order_by(user_filter)

    @app.get("/users_with_default_order_by", response_model=list[UserOut])
    async def get_users_with_default_order_by(
        user_filter: UserFilterOrderByWithDefault = FilterDepends(UserFilterOrderByWithDefault),
    ):
        return await get_users_with_order_by(user_filter)

    @app.get("/users_with_restricted_order_by", response_model=list[UserOut])
    async def get_users_with_restricted_order_by(
        user_filter: UserFilterRestrictedOrderBy = FilterDepends(UserFilterRestrictedOrderBy),
    ):
        return await get_users_with_order_by(user_filter)

    @app.get("/users_with_custom_order_by", response_model=list[UserOut])
    async def get_users_with_custom_order_by(
        user_filter: UserFilterCustomOrderBy = FilterDepends(UserFilterCustomOrderBy),
    ):
        return await get_users_with_order_by(user_filter)

    yield app
