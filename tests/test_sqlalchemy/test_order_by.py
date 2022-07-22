from typing import AsyncIterator

import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_filter import FilterDepends
from fastapi_filter.contrib.sqlalchemy import Filter


@pytest.fixture(scope="function")
def app(SessionLocal, Address, User, UserOut, UserFilterOrderBy, UserFilterOrderByWithDefault):
    app = FastAPI()

    async def get_db() -> AsyncIterator[AsyncSession]:
        async with SessionLocal() as session:
            yield session

    @app.get("/users", response_model=list[UserOut])
    async def get_users(
        user_filter: UserFilterOrderBy = FilterDepends(UserFilterOrderBy), db: AsyncSession = Depends(get_db)
    ):
        query = user_filter.sort(select(User))  # type: ignore[attr-defined]
        result = await db.execute(query)
        return result.scalars().all()

    @app.get("/users_with_default", response_model=list[UserOut])
    async def get_users_with_default(
        user_filter: UserFilterOrderByWithDefault = FilterDepends(UserFilterOrderByWithDefault),
        db: AsyncSession = Depends(get_db),
    ):
        query = user_filter.sort(select(User))  # type: ignore[attr-defined]
        result = await db.execute(query)
        return result.scalars().all()

    yield app


@pytest.fixture(scope="function")
async def test_client(app):
    async with AsyncClient(app=app, base_url="http://test") as async_test_client:
        yield async_test_client


@pytest.fixture(scope="function")
def UserFilterOrderByWithDefault(User):
    class UserFilterOrderByWithDefault(Filter):
        class Constants(Filter.Constants):
            model = User

        order_by: list[str] = ["age"]

    yield UserFilterOrderByWithDefault


@pytest.fixture(scope="function")
def UserFilterOrderBy(User):
    class UserFilterOrderBy(Filter):
        class Constants(Filter.Constants):
            model = User

        order_by: list[str] | None

    yield UserFilterOrderBy


@pytest.fixture(scope="function")
def UserFilterNoOrderBy(User):
    class UserFilterNoOrderBy(Filter):
        class Constants(Filter.Constants):
            model = User

    yield UserFilterNoOrderBy


@pytest.mark.parametrize(
    "order_by,assert_function",
    [
        [None, lambda previous_user, user: True],
        [
            ["name"],
            lambda previous_user, user: previous_user.name <= user.name if previous_user.name and user.name else True,
        ],
        [
            ["-created_at"],
            lambda previous_user, user: previous_user.created_at >= user.created_at,
        ],
        [
            ["age", "-name"],
            lambda previous_user, user: (previous_user.age < user.age)
            or (
                previous_user.age == user.age
                and (previous_user.name <= user.name if previous_user.name and user.name else True)
            ),
        ],
    ],
)
@pytest.mark.asyncio
async def test_basic_order_by(session, User, UserFilterOrderBy, users, order_by, assert_function):
    query = select(User)
    query = UserFilterOrderBy(order_by=order_by).sort(query)
    result = await session.execute(query)
    previous_user = None
    for user in result.scalars().all():
        if not previous_user:
            previous_user = user
            continue
        assert assert_function(previous_user, user)
        previous_user = user


@pytest.mark.parametrize(
    "order_by,assert_function",
    [
        [None, lambda previous_user, user: True],
        [
            "name",
            lambda previous_user, user: previous_user["name"] <= user["name"]
            if previous_user["name"] and user["name"]
            else True,
        ],
        [
            "-created_at",
            lambda previous_user, user: previous_user["created_at"] >= user["created_at"],
        ],
        [
            "age,-name",
            lambda previous_user, user: (previous_user["age"] < user["age"])
            or (
                previous_user["age"] == user["age"]
                and (previous_user["name"] <= user["name"] if previous_user["name"] and user["name"] else True)
            ),
        ],
    ],
)
@pytest.mark.asyncio
async def test_api_basic_order_by(session, test_client, users, order_by, assert_function):
    endpoint = "/users"
    if order_by is not None:
        endpoint = f"{endpoint}?order_by={order_by}"
    response = await test_client.get(endpoint)
    previous_user = None
    for user in response.json():
        if not previous_user:
            previous_user = user
            continue
        assert assert_function(previous_user, user)
        previous_user = user


@pytest.mark.asyncio
async def test_order_by_with_default(session, User, UserFilterOrderByWithDefault, users):
    query = select(User)
    query = UserFilterOrderByWithDefault().sort(query)
    result = await session.execute(query)
    previous_user = None
    for user in result.scalars().all():
        if not previous_user:
            previous_user = user
            continue
        assert previous_user.age <= user.age
        previous_user = user


@pytest.mark.parametrize(
    "order_by,assert_function",
    [
        [None, lambda previous_user, user: previous_user["age"] <= user["age"]],
        [
            "name",
            lambda previous_user, user: previous_user["name"] <= user["name"]
            if previous_user["name"] and user["name"]
            else True,
        ],
        [
            "-created_at",
            lambda previous_user, user: previous_user["created_at"] >= user["created_at"],
        ],
        [
            "age,-name",
            lambda previous_user, user: (previous_user["age"] < user["age"])
            or (
                previous_user["age"] == user["age"]
                and (previous_user["name"] <= user["name"] if previous_user["name"] and user["name"] else True)
            ),
        ],
    ],
)
@pytest.mark.asyncio
async def test_api_order_by_with_default(session, test_client, users, order_by, assert_function):
    endpoint = "/users_with_default"
    if order_by is not None:
        endpoint = f"{endpoint}?order_by={order_by}"
    response = await test_client.get(endpoint)
    previous_user = None
    for user in response.json():
        if not previous_user:
            previous_user = user
            continue
        assert assert_function(previous_user, user)
        previous_user = user


def test_invalid_order_by(UserFilterOrderBy):
    with pytest.raises(ValidationError):
        UserFilterOrderBy(order_by="invalid")


def test_missing_order_by_field(User, UserFilterNoOrderBy):
    query = select(User)
    with pytest.raises(AttributeError):
        UserFilterNoOrderBy().sort(query)
