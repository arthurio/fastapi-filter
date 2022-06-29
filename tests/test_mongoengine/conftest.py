from datetime import datetime
from typing import Any, Generator

import pytest
from bson.objectid import ObjectId
from mongoengine import Document, connect, fields
from pydantic import BaseModel, Field


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


@pytest.fixture(scope="session")
def AddressOut(PydanticObjectId):
    class AddressOut(BaseModel):
        id: PydanticObjectId = Field(..., alias="_id")
        street: str | None
        city: str
        country: str

        class Config:
            orm_mode = True

    yield AddressOut


@pytest.fixture(scope="session")
def UserOut(PydanticObjectId, AddressOut):
    class UserOut(BaseModel):
        id: PydanticObjectId = Field(..., alias="_id")
        created_at: datetime
        name: str | None
        age: int
        address: AddressOut | None

        class Config:
            orm_mode = True

    yield UserOut


@pytest.fixture(scope="function", autouse=True)
def clear_database(User):
    User.drop_collection()
    yield
    User.drop_collection()
