import logging
from typing import Any, List, Optional

import uvicorn
from faker import Faker
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, EmailStr

from fastapi_filter import FilterDepends, with_prefix
from fastapi_filter.contrib.elasticsearch_dsl import Filter

fake = Faker()

logger = logging.getLogger("uvicorn")
from datetime import datetime
from fnmatch import fnmatch

from elasticsearch_dsl import Document, Keyword, connections, Integer, Nested, SearchAsYouType, InnerDoc


ALIAS = "address"
PATTERN = ALIAS + "-*"


class Address(InnerDoc):
    street = Keyword()
    city = SearchAsYouType()
    country = Keyword()
    number = Integer()


class User(Document):
    name = SearchAsYouType()
    email = Keyword()
    age = Integer()
    address = Nested(Address)

    @classmethod
    def _matches(cls, hit):
        return fnmatch(hit["_index"], PATTERN)

    class Index:
        name = ALIAS
        settings = {"number_of_shards": 1, "number_of_replicas": 0}


def setup():
    index_template = User._index.as_template(ALIAS, PATTERN)
    index_template.save()

    if not User._index.exists():
        migrate(move_data=False)


def migrate(move_data=True, update_alias=True):
    # construct a new index name by appending current timestamp
    next_index = PATTERN.replace("*", datetime.now().strftime("%Y%m%d%H%M%S%f"))
    es = connections.get_connection()
    # create new index, it will use the settings from the template
    es.indices.create(index=next_index)
    if move_data:
        # move data from current alias to the new index
        es.reindex(
            body={"source": {"index": ALIAS}, "dest": {"index": next_index}},
            request_timeout=3600,
        )
        # refresh the index to make the changes visible
        es.indices.refresh(index=next_index)

    if update_alias:
        # repoint the alias to point to the newly created index
        es.indices.update_aliases(
            body={
                "actions": [
                    {"remove": {"alias": ALIAS, "index": PATTERN}},
                    {"add": {"alias": ALIAS, "index": next_index}},
                ]
            }
        )


class AddressOut(BaseModel):
    street: Optional[str] = None
    city: str
    number: int
    country: str

    class Config:
        orm_mode = True


class UserIn(BaseModel):
    name: str
    email: EmailStr
    age: int


class UserOut(UserIn):
    model_config = ConfigDict(from_attributes=True)

    name: str
    email: EmailStr
    age: int
    address: Optional[AddressOut] = None


class AddressFilter(Filter):
    street: Optional[str] = None
    number: Optional[int] = None
    number__gt: Optional[int] = None
    number__gte: Optional[int] = None
    number__lt: Optional[int] = None
    number__lte: Optional[int] = None
    street__isnull: Optional[bool] = None
    country: Optional[str] = None
    country_not: Optional[str] = None
    city: Optional[str] = None
    city__in: Optional[List[str]] = None
    city__not_in: Optional[List[str]] = ["city"]
    custom_order_by: Optional[List[str]] = None
    custom_search: Optional[str] = None
    order_by: List[str] = ["-street"]

    class Constants(Filter.Constants):
        model = Address
        # ordering_field_name = "street"
        search_field_name = "custom_search"
        search_model_fields = ["street", "country", "city"]


class UserFilter(Filter):
    name: Optional[str] = None
    address: Optional[AddressFilter] = FilterDepends(with_prefix("address", AddressFilter))
    age__lt: Optional[int] = None
    # age__gte: int = Field(Query(description="this is a nice description"))
    """Required field with a custom description.

    See: https://github.com/tiangolo/fastapi/issues/4700 for why we need to wrap `Query` in `Field`.
    """
    order_by: List[str] = ["-age"]
    search: Optional[str] = None

    class Constants(Filter.Constants):
        model = User
        search_model_fields = ["name"]


app = FastAPI()


@app.on_event("startup")
async def on_startup() -> None:
    connections.create_connection(hosts="http://localhost:9200")

    setup()
    migrate()

    for i in range(100):
        if i % 5 == 0:
            address = Address(
                street=fake.street_address(),
                city=fake.city(),
                country=fake.country(),
                number=fake.random_int(min=5, max=100),
            )
        else:
            address = Address(city=fake.city(), country=fake.country(), number=fake.random_int(min=5, max=100))
        user = User(name=fake.name(), email=fake.email(), age=fake.random_int(min=5, max=120), address=address)
        user.save()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    s = Address.search().query("match_all")
    s.delete()


@app.get("/users", response_model=List[UserOut])
async def get_users(
    user_filter: UserFilter = FilterDepends(with_prefix("my_custom_prefix", UserFilter), by_alias=True),
) -> Any:
    query = user_filter.filter(User.search())
    query = user_filter.sort(query)
    response = query.execute()
    return [UserOut(**user.to_dict()) for user in response]


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)
