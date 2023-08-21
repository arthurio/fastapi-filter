import logging
from typing import Any, Dict, Generator, List, Optional

import click
import uvicorn
from bson.objectid import ObjectId
from faker import Faker
from fastapi import FastAPI, Query
from mongoengine import Document, connect, fields
from pydantic import BaseModel, ConfigDict, EmailStr, Field, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from fastapi_filter import FilterDepends, with_prefix
from fastapi_filter.contrib.mongoengine import Filter

fake = Faker()

logger = logging.getLogger("uvicorn")


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
    model_config = ConfigDict(from_attributes=True)

    id: PydanticObjectId = Field(..., alias="_id")
    name: str
    email: EmailStr
    age: int
    address: Optional[AddressOut] = None


class AddressFilter(Filter):
    street: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    city__in: Optional[List[str]] = None
    custom_order_by: Optional[List[str]] = None
    custom_search: Optional[str] = None

    class Constants(Filter.Constants):
        model = Address
        ordering_field_name = "custom_order_by"
        search_field_name = "custom_search"
        search_model_fields = ["street", "country", "city"]


address_filter, address_filter_annotated = with_prefix("address", AddressFilter)


class UserFilter(Filter):
    name: Optional[str] = None
    address: Optional[address_filter_annotated] = FilterDepends(address_filter)
    age__lt: Optional[int] = None
    age__gte: int = Field(Query(description="this is a nice description"))
    """Required field with a custom description.

    See: https://github.com/tiangolo/fastapi/issues/4700 for why we need to wrap `Query` in `Field`.
    """
    order_by: List[str] = ["age"]
    search: Optional[str] = None

    class Constants(Filter.Constants):
        model = User
        search_model_fields = ["name"]


app = FastAPI()


@app.on_event("startup")
async def on_startup() -> None:
    message = "Open http://127.0.0.1:8000/docs to start exploring 🎒 🧭 🗺️"
    color_message = "Open " + click.style("http://127.0.0.1:8000/docs", bold=True) + " to start exploring 🎒 🧭 🗺️"
    logger.info(message, extra={"color_message": color_message})

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
    address_filter: AddressFilter = FilterDepends(address_filter, by_alias=True),
) -> Any:
    query = address_filter.filter(Address.objects())
    query = address_filter.sort(query)
    return [address.to_mongo() for address in query]


if __name__ == "__main__":
    uvicorn.run("fastapi_filter_mongoengine:app", reload=True)
