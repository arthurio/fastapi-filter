from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from fastapi_filter import FilterDepends, with_prefix
from fastapi_filter.contrib.mongoengine import Filter


@pytest.fixture(scope="function")
def app(db_connect, Address, User, UserFilter, UserOut):
    app = FastAPI()

    @app.get("/users", response_model=list[UserOut])
    async def get_users(user_filter: UserFilter = FilterDepends(UserFilter)):
        query = user_filter.filter(User.objects()).select_related()  # type: ignore[attr-defined]
        return [user.to_mongo() | {"address": user.address.to_mongo() if user.address else None} for user in query]

    yield app


@pytest.fixture(scope="function")
async def test_client(app):
    async with AsyncClient(app=app, base_url="http://test") as async_test_client:
        yield async_test_client


@pytest.fixture(scope="session")
def AddressFilter(Address):
    class AddressFilter(Filter):
        street__isnull: bool | None
        country: str | None
        city: str | None
        city__in: list[str] | None
        country__nin: list[str] | None

        class Constants(Filter.Constants):
            model = Address

    yield AddressFilter


@pytest.fixture(scope="session")
def UserFilter(User, AddressFilter):
    class UserFilter(Filter):
        name: str | None
        name__in: list[str] | None
        name__nin: list[str] | None
        name__ne: str | None
        name__isnull: bool | None
        age: int | None
        age__lt: int | None
        age__lte: int | None
        age__gt: int | None
        age__gte: int | None
        age__in: list[int] | None
        address: AddressFilter | None = FilterDepends(with_prefix("address", AddressFilter))

        class Constants(Filter.Constants):
            model = User

    yield UserFilter


@pytest.mark.parametrize(
    "filter_,expected_count",
    [
        [{"name": "Mr Praline"}, 1],
        [{"name__isnull": True}, 1],
        [{"name__nin": "Mr Praline,Mr Creosote,Gumbys,Knight"}, 3],
        [{"name__isnull": False}, 5],
        [{"name__ne": "Mr Praline"}, 5],
        [{"name__ne": "Mr Praline", "age__gte": 21, "age__lt": 50}, 2],
        [{"age__in": [1]}, 1],
        [{"age__in": "1"}, 1],
        [{"age__in": "21,33"}, 3],
        [{"address": {"country__nin": "France"}}, 3],
        [{"address": {"street__isnull": True}}, 1],
        [{"address": {"city__in": "Nantes,Denver"}}, 3],
        [{"address": {"city": "San Francisco"}}, 1],
    ],
)
def test_basic_filter(User, UserFilter, Address, users, filter_, expected_count):
    query = UserFilter(**filter_).filter(User.objects())
    assert query.count() == expected_count


@pytest.mark.parametrize(
    "filter_,expected_count",
    [
        [{"name": "Mr Praline"}, 1],
        [{"name__in": "Mr Praline,Mr Creosote,Gumbys,Knight"}, 3],
        [{"name__isnull": True}, 1],
        [{"name__isnull": False}, 5],
        [{"name__nin": "Mr Praline,Mr Creosote,Gumbys,Knight"}, 3],
        [{"name__ne": "Mr Praline"}, 5],
        [{"name__ne": "Mr Praline", "age__gte": 21, "age__lt": 50}, 2],
        [{"age__in": [1]}, 1],
        [{"age__in": "1"}, 1],
        [{"age__in": "21,33"}, 3],
        [{"address__country__nin": "France"}, 3],
        [{"address__street__isnull": True}, 1],
        [{"address__city__in": "Nantes,Denver"}, 3],
        [{"address__city": "San Francisco"}, 1],
    ],
)
async def test_api(test_client, Address, User, UserFilter, users, filter_, expected_count):
    response = await test_client.get(f"/users?{urlencode(filter_)}")
    assert len(response.json()) == expected_count
