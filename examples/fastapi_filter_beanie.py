import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated, Any

import click
import uvicorn
from beanie import Document, Link, PydanticObjectId, init_beanie
from beanie.odm.fields import WriteRules
from faker import Faker
from fastapi import FastAPI, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pymongo import AsyncMongoClient

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

    model_config = ConfigDict(from_attributes=True)


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
    address: AddressOut | None = None


class AddressFilter(Filter):
    street: str | None = None
    country: str | None = None
    city: str | None = None
    city__in: list[str] | None = None
    custom_order_by: list[str] | None = None
    custom_search: str | None = None

    class Constants(Filter.Constants):
        model = Address
        ordering_field_name = "custom_order_by"
        search_field_name = "custom_search"
        search_model_fields = ["street", "country", "city"]


class UserFilter(Filter):
    name: str | None = None
    address: AddressFilter | None = FilterDepends(with_prefix("address", AddressFilter))
    age__lt: int | None = None
    age__gte: int = Field(Query(description="this is a nice description"))
    """Required field with a custom description.

    See: https://github.com/tiangolo/fastapi/issues/4700 for why we need to wrap `Query` in `Field`.
    """
    order_by: list[str] = ["age"]
    search: str | None = None

    class Constants(Filter.Constants):
        model = User
        search_model_fields = ["name"]


class FlatUserFilter(Filter):
    """Flat user filter with no nested sub-filters.

    Suitable for use with the native ``Annotated[FlatUserFilter, Query()]`` pattern
    (FastAPI 0.115+). For nested filters (e.g. address sub-filter via ``with_prefix``),
    use ``FilterDepends`` instead — see the ``UserFilter`` class above.
    """

    name: str | None = None
    age__lt: int | None = None
    age__gte: int | None = None
    order_by: list[str] = ["age"]
    search: str | None = None

    class Constants(Filter.Constants):
        model = User
        search_model_fields = ["name"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    message = "Open http://127.0.0.1:8000/docs to start exploring 🎒 🧭 🗺️"
    color_message = "Open " + click.style("http://127.0.0.1:8000/docs", bold=True) + " to start exploring 🎒 🧭 🗺️"
    logger.info(message, extra={"color_message": color_message})

    client: AsyncMongoClient = AsyncMongoClient("mongodb://localhost:27017/fastapi_filter")
    db = client.fastapi_filter
    await init_beanie(database=db, document_models=[Address, User])

    for _ in range(100):
        address = Address(street=fake.street_address(), city=fake.city(), country=fake.country())
        await address.save()
        user = User(name=fake.name(), email=fake.email(), age=fake.random_int(min=5, max=120), address=address)
        await user.save(link_rule=WriteRules.WRITE)

    yield

    await Address.find_all().delete()
    await User.find_all().delete()
    await client.close()


app = FastAPI(lifespan=lifespan)


@app.get("/users", response_model=list[UserOut])
async def get_users(user_filter: UserFilter = FilterDepends(UserFilter)) -> Any:
    query = user_filter.filter(User.find({}))
    query = user_filter.sort(query)
    query = query.find(fetch_links=True)
    return await query.project(UserOut).to_list()


@app.get("/users-native", response_model=list[UserOut])
async def get_users_native(
    # For non-nested filters, the native Annotated[Filter, Query()] pattern (FastAPI 0.115+)
    # is simpler and does not require FilterDepends. Use FilterDepends when you need
    # nested filters with with_prefix() — see the /users route above.
    user_filter: Annotated[FlatUserFilter, Query()],
) -> Any:
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
