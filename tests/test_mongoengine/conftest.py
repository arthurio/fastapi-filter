import sys
from datetime import datetime
from typing import Any, List, Optional

if sys.version_info >= (3, 9):
    from typing import Annotated
else:
    from typing_extensions import Annotated

import pytest
from bson.objectid import ObjectId
from fastapi import FastAPI, Query
from mongoengine import Document, connect, fields
from pydantic import BaseModel, ConfigDict, Field, GetCoreSchemaHandler, field_validator
from pydantic_core import CoreSchema, core_schema

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
        def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
            return core_schema.no_info_after_validator_function(
                cls.validate,
                core_schema.is_instance_schema(cls=ObjectId),
                serialization=core_schema.plain_serializer_function_ser_schema(
                    str,
                    info_arg=False,
                    return_schema=core_schema.str_schema(),
                ),
            )

        @staticmethod
        def validate(v: ObjectId) -> ObjectId:
            if not ObjectId.is_valid(v):
                raise ValueError("Invalid objectid")
            return v

    return PydanticObjectId


@pytest.fixture(scope="session")
def User(db_connect, Address, Sport):
    class User(Document):
        created_at = fields.DateTimeField()
        name = fields.StringField(null=True)
        email = fields.EmailField()
        age = fields.IntField()
        address = fields.ReferenceField(Address)
        favorite_sports = fields.ListField(fields.ReferenceField(Sport))

    return User


@pytest.fixture(scope="session")
def Address(db_connect):
    class Address(Document):
        street = fields.StringField(null=True)
        city = fields.StringField()
        country = fields.StringField()

    return Address


@pytest.fixture(scope="session")
def Sport(db_connect):
    class Sport(Document):
        name = fields.StringField()
        is_individual = fields.BooleanField()

    return Sport


@pytest.fixture(scope="function")
def sports(Sport):
    sports = [
        Sport(name="Ice Hockey", is_individual=False).save(),
        Sport(name="Tennis", is_individual=True).save(),
    ]

    yield sports


@pytest.fixture(scope="function")
def users(User, Address, sports):
    users = [
        User(
            name=None,
            age=21,
            created_at=datetime(2021, 12, 1),
            favorite_sports=sports,
        ).save(),
        User(
            name="Mr Praline",
            age=33,
            created_at=datetime(2021, 12, 1),
            address=Address(street="22 rue Bellier", city="Nantes", country="France").save(),
            favorite_sports=[sports[0]],
        ).save(),
        User(
            name="The colonel",
            age=90,
            created_at=datetime(2021, 12, 2),
            address=Address(street="Wrench", city="Bathroom", country="Clue").save(),
            favorite_sports=[sports[1]],
        ).save(),
        User(
            name="Mr Creosote",
            age=21,
            created_at=datetime(2021, 12, 3),
            address=Address(city="Nantes", country="France").save(),
        ).save(),
        User(
            name="Rabbit of Caerbannog",
            age=1,
            created_at=datetime(2021, 12, 4),
            address=Address(street="1234 street", city="San Francisco", country="United States").save(),
        ).save(),
        User(
            name="Gumbys",
            age=50,
            created_at=datetime(2021, 12, 4),
            address=Address(street="4567 avenue", city="Denver", country="United States").save(),
        ).save(),
    ]
    yield users


@pytest.fixture(scope="package")
def AddressFilter(Address, Filter):
    class AddressFilter(Filter):  # type: ignore[misc, valid-type]
        street__isnull: Optional[bool] = None
        country: Optional[str] = None
        city: Optional[str] = None
        city__in: Optional[List[str]] = None
        country__nin: Optional[List[str]] = None

        class Constants(Filter.Constants):  # type: ignore[name-defined]
            model = Address

    yield AddressFilter


@pytest.fixture(scope="package")
def UserFilter(User, Filter, AddressFilter):
    address_with_prefix, plain_validator = with_prefix("address", AddressFilter)

    class UserFilter(Filter):  # type: ignore[misc, valid-type]
        name: Optional[str] = None
        name__in: Optional[List[str]] = None
        name__nin: Optional[List[str]] = None
        name__ne: Optional[str] = None
        name__isnull: Optional[bool] = None
        age: Optional[int] = None
        age__lt: Optional[int] = None
        age__lte: Optional[int] = None
        age__gt: Optional[int] = None
        age__gte: Optional[int] = None
        age__in: Optional[List[int]] = None
        address: Optional[Annotated[AddressFilter, plain_validator]] = FilterDepends(  # type: ignore[valid-type]
            address_with_prefix
        )
        search: Optional[str] = None

        class Constants(Filter.Constants):  # type: ignore[name-defined]
            model = User
            search_model_fields = ["name", "email"]
            search_field_name = "search"
            ordering_field_name = "order_by"

    yield UserFilter


@pytest.fixture(scope="package")
def SportFilter(Sport, Filter):
    class SportFilter(Filter):  # type: ignore[misc, valid-type]
        name: Optional[str] = Field(Query(description="Name of the sport", default=None))
        is_individual: bool
        bogus_filter: Optional[str] = None

        class Constants(Filter.Constants):  # type: ignore [name-defined]
            model = Sport

        @field_validator("bogus_filter")
        def throw_exception(cls, value):
            if value:
                raise ValueError("You can't use this bogus filter")

    yield SportFilter


@pytest.fixture(scope="package")
def AddressOut(PydanticObjectId):
    class AddressOut(BaseModel):
        model_config = ConfigDict(from_attributes=True)

        id: PydanticObjectId = Field(..., alias="_id")  # type: ignore[valid-type]
        street: Optional[str] = None
        city: str
        country: str

    yield AddressOut


@pytest.fixture(scope="package")
def UserOut(PydanticObjectId, AddressOut):
    class UserOut(BaseModel):
        model_config = ConfigDict(from_attributes=True)

        id: PydanticObjectId = Field(..., alias="_id")  # type: ignore[valid-type]
        created_at: datetime
        name: Optional[str] = None
        age: int
        address: Optional[AddressOut] = None  # type: ignore[valid-type]

    yield UserOut


@pytest.fixture(scope="package")
def SportOut(PydanticObjectId):
    class SportOut(BaseModel):
        model_config = ConfigDict(from_attributes=True)

        id: PydanticObjectId = Field(..., alias="_id")  # type: ignore[valid-type]
        name: str
        is_individual: bool

    yield SportOut


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
    SportFilter,
    SportOut,
    Sport,
    UserFilter,
    UserFilterCustomOrderBy,
    UserFilterOrderBy,
    UserFilterOrderByWithDefault,
    UserFilterRestrictedOrderBy,
    UserOut,
):
    app = FastAPI()

    @app.get("/users", response_model=List[UserOut])  # type: ignore[valid-type]
    async def get_users(user_filter: UserFilter = FilterDepends(UserFilter)):  # type: ignore[valid-type]
        query = user_filter.filter(User.objects())  # type: ignore[attr-defined]
        query = query.select_related()
        return [
            {
                **user.to_mongo(),
                "address": user.address.to_mongo() if user.address else None,
                "favorite_sports": [sport.to_mongo() for sport in user.favorite_sports],
            }
            for user in query
        ]

    @app.get("/users_with_order_by", response_model=List[UserOut])  # type: ignore[valid-type]
    async def get_users_with_order_by(
        user_filter: UserFilterOrderBy = FilterDepends(UserFilterOrderBy),  # type: ignore[valid-type]
    ):
        query = user_filter.sort(User.objects())  # type: ignore[attr-defined]
        query = user_filter.filter(query)  # type: ignore[attr-defined]
        query = query.select_related()
        return [
            {
                **user.to_mongo(),
                "address": user.address.to_mongo() if user.address else None,
                "favorite_sports": [sport.to_mongo() for sport in user.favorite_sports],
            }
            for user in query
        ]

    @app.get("/users_with_no_order_by", response_model=List[UserOut])  # type: ignore[valid-type]
    async def get_users_with_no_order_by(
        user_filter: UserFilter = FilterDepends(UserFilter),  # type: ignore[valid-type]
    ):
        return await get_users_with_order_by(user_filter)

    @app.get("/users_with_default_order_by", response_model=List[UserOut])  # type: ignore[valid-type]
    async def get_users_with_default_order_by(
        user_filter: UserFilterOrderByWithDefault = FilterDepends(  # type: ignore[valid-type]
            UserFilterOrderByWithDefault
        ),
    ):
        return await get_users_with_order_by(user_filter)

    @app.get("/users_with_restricted_order_by", response_model=List[UserOut])  # type: ignore[valid-type]
    async def get_users_with_restricted_order_by(
        user_filter: UserFilterRestrictedOrderBy = FilterDepends(  # type: ignore[valid-type]
            UserFilterRestrictedOrderBy
        ),
    ):
        return await get_users_with_order_by(user_filter)

    @app.get("/users_with_custom_order_by", response_model=List[UserOut])  # type: ignore[valid-type]
    async def get_users_with_custom_order_by(
        user_filter: UserFilterCustomOrderBy = FilterDepends(UserFilterCustomOrderBy),  # type: ignore[valid-type]
    ):
        return await get_users_with_order_by(user_filter)

    @app.get("/sports", response_model=List[SportOut])  # type: ignore[valid-type]
    async def get_sports(
        sport_filter: SportFilter = FilterDepends(SportFilter),  # type: ignore[valid-type]
    ):
        query = sport_filter.filter(Sport.objects())  # type: ignore[attr-defined]
        return [sport.to_mongo() for sport in query]

    yield app
