from typing import AsyncIterator
from urllib.parse import urlencode

import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from fastapi_filter import FilterDepends, with_prefix
from fastapi_filter.contrib.sqlalchemy import Filter


@pytest.fixture(scope="function")
def app(SessionLocal, Address, User, UserFilter, UserOut):
    app = FastAPI()

    async def get_db() -> AsyncIterator[AsyncSession]:
        async with SessionLocal() as session:
            yield session

    @app.get("/users", response_model=list[UserOut])
    async def get_users(user_filter: UserFilter = FilterDepends(UserFilter), db: AsyncSession = Depends(get_db)):
        query = user_filter.filter(select(User).outerjoin(Address))  # type: ignore[attr-defined]
        result = await db.execute(query)
        return result.scalars().all()

    yield app


@pytest.fixture(scope="function")
async def test_client(app):
    async with AsyncClient(app=app, base_url="http://test") as async_test_client:
        yield async_test_client


@pytest.fixture(scope="session")
def AddressFilter(Address):
    class AddressFilter(Filter):
        street__isnull: bool | None
        city: str | None
        city__in: list[str] | None
        country__not_in: list[str] | None

        class Constants:
            model = Address

    yield AddressFilter


@pytest.fixture(scope="session")
def UserFilter(User, AddressFilter):
    class UserFilter(Filter):
        name: str | None
        name__in: list[str] | None
        name__not: str | None
        name__not_in: list[str] | None
        name__isnull: bool | None
        age: int | None
        age__lt: int | None
        age__lte: int | None
        age__gt: int | None
        age__gte: int | None
        age__in: list[int] | None
        address: AddressFilter | None = FilterDepends(with_prefix("address", AddressFilter))
        address_id__isnull: bool | None

        class Constants:
            model = User

    yield UserFilter


@pytest.mark.parametrize(
    "filter_,expected_count",
    [
        [{"name": "Mr Praline"}, 1],
        [{"name__in": "Mr Praline,Mr Creosote,Gumbys,Knight"}, 3],
        [{"name__isnull": True}, 1],
        [{"name__isnull": False}, 5],
        [{"name__not_in": "Mr Praline,Mr Creosote,Gumbys,Knight"}, 2],
        [{"name__not": "Mr Praline"}, 5],
        [{"name__not": "Mr Praline", "age__gte": 21, "age__lt": 50}, 2],
        [{"age__in": [1]}, 1],
        [{"age__in": "1"}, 1],
        [{"age__in": "21,33"}, 3],
        [{"address": {"country__not_in": "France"}}, 3],
        [{"address": {"street__isnull": True}}, 2],
        [{"address": {"city__in": "Nantes,Denver"}}, 3],
        [{"address": {"city": "San Francisco"}}, 1],
        [{"address_id__isnull": True}, 1],
    ],
)
async def test_filter(session, Address, User, UserFilter, users, filter_, expected_count):
    query = select(User).outerjoin(Address)
    query = UserFilter(**filter_).filter(query)

    result = await session.execute(query)
    assert len(result.scalars().all()) == expected_count


@pytest.mark.parametrize(
    "filter_,expected_count",
    [
        [{"name": "Mr Praline"}, 1],
        [{"name__in": "Mr Praline,Mr Creosote,Gumbys,Knight"}, 3],
        [{"name__isnull": True}, 1],
        [{"name__isnull": False}, 5],
        [{"name__not_in": "Mr Praline,Mr Creosote,Gumbys,Knight"}, 2],
        [{"name__not": "Mr Praline"}, 5],
        [{"name__not": "Mr Praline", "age__gte": 21, "age__lt": 50}, 2],
        [{"age__in": [1]}, 1],
        [{"age__in": "1"}, 1],
        [{"age__in": "21,33"}, 3],
        [{"address__country__not_in": "France"}, 3],
        [{"address__street__isnull": True}, 2],
        [{"address__city__in": "Nantes,Denver"}, 3],
        [{"address__city": "San Francisco"}, 1],
        [{"address_id__isnull": True}, 1],
    ],
)
async def test_api(test_client, Address, User, UserFilter, users, filter_, expected_count):
    response = await test_client.get(f"/users?{urlencode(filter_)}")
    assert len(response.json()) == expected_count
