import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Optional

import click
import uvicorn
from beanie import Document, Link, PydanticObjectId, init_beanie
from beanie.odm.fields import WriteRules
from faker import Faker
from fastapi import FastAPI, Query
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from fastapi_filter import FilterDepends, with_prefix
from fastapi_filter.contrib.beanie import Filter

fake = Faker()

logger = logging.getLogger("uvicorn")


class Address(Document):
    street: str
    city: str
    country: str


class User(Document):
    name: str
    email: EmailStr
    age: int
    address: Link[Address]


class AddressOut(BaseModel):
    id: PydanticObjectId = Field(alias="_id", description="MongoDB document ObjectID")
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

    id: PydanticObjectId = Field(alias="_id", description="MongoDB document ObjectID")
    name: str
    email: EmailStr
    age: int
    address: Optional[AddressOut] = None


class AddressFilter(Filter):
    street: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    city__in: Optional[list[str]] = None
    custom_order_by: Optional[list[str]] = None
    custom_search: Optional[str] = None

    class Constants(Filter.Constants):
        model = Address
        ordering_field_name = "custom_order_by"
        search_field_name = "custom_search"
        search_model_fields = ["street", "country", "city"]


class UserFilter(Filter):
    name: Optional[str] = None
    address: Optional[AddressFilter] = FilterDepends(with_prefix("address", AddressFilter))
    age__lt: Optional[int] = None
    age__gte: int = Field(Query(description="this is a nice description"))
    """Required field with a custom description.

    See: https://github.com/tiangolo/fastapi/issues/4700 for why we need to wrap `Query` in `Field`.
    """
    order_by: list[str] = ["age"]
    search: Optional[str] = None

    class Constants(Filter.Constants):
        model = User
        search_model_fields = ["name"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    message = "Open http://127.0.0.1:8000/docs to start exploring 🎒 🧭 🗺️"
    color_message = "Open " + click.style("http://127.0.0.1:8000/docs", bold=True) + " to start exploring 🎒 🧭 🗺️"
    logger.info(message, extra={"color_message": color_message})

    client: AsyncIOMotorClient = AsyncIOMotorClient("mongodb://localhost:27017/fastapi_filter")
    # https://github.com/tiangolo/fastapi/issues/3855#issuecomment-1013148113
    client.get_io_loop = asyncio.get_event_loop  # type: ignore[method-assign]
    db = client.fastapi_filter
    await init_beanie(database=db, document_models=[Address, User])

    for _ in range(100):
        address = Address(street=fake.street_address(), city=fake.city(), country=fake.country())
        await address.save()
        user = User(name=fake.name(), email=fake.email(), age=fake.random_int(min=5, max=120), address=address)
        await user.save(link_rule=WriteRules.WRITE)

    yield

    Address.find_all().delete()
    User.find_all().delete()
    client.close()


app = FastAPI(lifespan=lifespan)


@app.get("/users", response_model=list[UserOut])
async def get_users(user_filter: UserFilter = FilterDepends(UserFilter)) -> Any:
    query = user_filter.filter(User.find({}))
    query = user_filter.sort(query)
    query = query.find(fetch_links=True)
    return await query.project(UserOut).to_list()


@app.get("/addresses", response_model=list[AddressOut])
async def get_addresses(
    address_filter: AddressFilter = FilterDepends(with_prefix("my_custom_prefix", AddressFilter), by_alias=True),
) -> Any:
    query = address_filter.filter(Address.find({}))
    query = address_filter.sort(query)
    return await query.project(AddressOut).to_list()


if __name__ == "__main__":
    uvicorn.run("fastapi_filter_beanie:app", reload=True)
