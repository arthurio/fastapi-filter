from typing import Any, Dict, Generator, List, Optional

import uvicorn
from bson.objectid import ObjectId
from faker import Faker
from fastapi import FastAPI, Query
from mongoengine import Document, connect, fields
from pydantic import BaseModel, EmailStr, Field

from fastapi_filter import FilterDepends, with_prefix
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
    email: EmailStr
    age: int


class UserOut(UserIn):
    id: PydanticObjectId = Field(..., alias="_id")
    name: str
    email: EmailStr
    age: int
    address: Optional[AddressOut]

    class Config:
        orm_mode = True


class AddressFilter(Filter):
    street: Optional[str]
    country: Optional[str]
    city: Optional[str]
    city__in: Optional[List[str]]
    custom_order_by: Optional[List[str]]

    class Constants(Filter.Constants):
        model = Address
        ordering_field_name = "custom_order_by"


class UserFilter(Filter):
    name: Optional[str]
    address: Optional[AddressFilter] = FilterDepends(with_prefix("address", AddressFilter))
    age__lt: Optional[int]
    age__gte: int = Field(Query(description="this is a nice description"))
    """Required field with a custom description.

    See: https://github.com/tiangolo/fastapi/issues/4700 for why we need to wrap `Query` in `Field`.
    """
    order_by: List[str] = ["age"]

    class Constants(Filter.Constants):
        model = User


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


@app.get("/users", response_model=List[UserOut])
async def get_users(user_filter: UserFilter = FilterDepends(UserFilter)) -> Any:
    query = user_filter.filter(User.objects())
    query = user_filter.sort(query)
    query = query.select_related()
    return [{**user.to_mongo(), "address": user.address.to_mongo()} for user in query]


@app.get("/addresses", response_model=List[AddressOut])
async def get_addresses(
    address_filter: AddressFilter = FilterDepends(with_prefix("my_prefix", AddressFilter), by_alias=True),
) -> Any:
    query = address_filter.filter(Address.objects())
    query = address_filter.sort(query)
    return [address.to_mongo() for address in query]


if __name__ == "__main__":
    uvicorn.run("fastapi_filter_mongoengine:app", reload=True)
