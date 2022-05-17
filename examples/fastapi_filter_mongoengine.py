from typing import Any, Dict, Generator

import uvicorn
from bson.objectid import ObjectId
from faker import Faker
from fastapi import FastAPI
from mongoengine import Document, connect, fields
from pydantic import BaseModel, Field

from fastapi_filter import FilterDepends, nested_filter
from fastapi_filter.contrib.mongoengine import Filter

fake = Faker()


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
    def __modify_schema__(cls, field_schema: Dict[str, Any]) -> None:
        field_schema.update(type="string")


class Address(Document):
    street = fields.StringField()
    city = fields.StringField()
    country = fields.StringField()


class User(Document):
    name = fields.StringField()
    email = fields.EmailField()
    age = fields.IntField()
    address = fields.ReferenceField(Address)


class AddressOut(BaseModel):
    id: PydanticObjectId = Field(..., alias="_id")
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
    id: PydanticObjectId = Field(..., alias="_id")
    address: AddressOut | None

    class Config:
        orm_mode = True


class AddressFilter(Filter):
    street: str | None
    country: str | None
    city: str | None = "Nantes"
    city__in: list[str] | None

    class Constants:
        collection = Address


class UserFilter(Filter):
    name: str | None
    address: AddressFilter | None = FilterDepends(nested_filter("address", AddressFilter))
    age__lt: int | None
    age__gte: int  # <-- NOTE(arthurio): This filter required

    class Constants:
        collection = User


app = FastAPI()


@app.on_event("startup")
async def on_startup() -> None:
    connect(host="mongodb://localhost:27017/fastapi_filter")
    for _ in range(100):
        address = Address(street=fake.street_address(), city=fake.city(), country=fake.country())
        address.save()
        user = User(name=fake.name(), email=fake.email(), age=fake.random_int(min=5, max=120), address=address)
        user.save()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    Address.drop_collection()
    User.drop_collection()


@app.get("/users", response_model=list[UserOut])
async def get_users(user_filter: UserFilter = FilterDepends(UserFilter)) -> Any:
    query = user_filter.filter(User.objects()).select_related()
    return [user.to_mongo() | {"address": user.address.to_mongo()} for user in query]


if __name__ == "__main__":
    uvicorn.run("fastapi_filter_mongoengine:app", reload=True)
