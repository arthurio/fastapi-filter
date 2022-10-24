import pytest
from fastapi import status
from pydantic import ValidationError
from sqlalchemy import select


@pytest.mark.parametrize(
    "order_by,assert_function",
    [
        [None, lambda previous_user, user: True],
        [[], lambda previous_user, user: True],
        [
            ["name"],
            lambda previous_user, user: previous_user.name <= user.name if previous_user.name and user.name else True,
        ],
        [
            ["-created_at"],
            lambda previous_user, user: previous_user.created_at >= user.created_at,
        ],
        [
            ["age", "-created_at"],
            lambda previous_user, user: (previous_user.age < user.age)
            or (previous_user.age == user.age and previous_user.created_at >= user.created_at),
        ],
    ],
)
@pytest.mark.asyncio
async def test_order_by(session, User, UserFilterOrderBy, users, order_by, assert_function):
    query = select(User)
    query = UserFilterOrderBy(order_by=order_by).sort(query)
    result = await session.execute(query)
    previous_user = None
    for user in result.scalars().unique().all():
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
    for user in result.scalars().unique().all():
        if not previous_user:
            previous_user = user
            continue
        assert previous_user.age <= user.age
        previous_user = user


@pytest.mark.parametrize(
    "order_by,assert_function",
    [
        [None, lambda previous_user, user: previous_user["age"] <= user["age"]],
        ["", lambda previous_user, user: True],
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


@pytest.mark.parametrize(
    "order_by,assert_function",
    [
        [None, lambda previous_user, user: True],
        ["", lambda previous_user, user: True],
        [
            "name",
            lambda previous_user, user: previous_user.name <= user.name if previous_user.name and user.name else True,
        ],
        [
            "-created_at",
            lambda previous_user, user: previous_user.created_at >= user.created_at,
        ],
        [
            "age,-name",
            lambda previous_user, user: (previous_user.age < user.age)
            or (
                previous_user.age == user.age
                and (previous_user.name <= user.name if previous_user.name and user.name else True)
            ),
        ],
    ],
)
@pytest.mark.asyncio
async def test_custom_order_by(User, users, UserFilterCustomOrderBy, session, order_by, assert_function):
    query = select(User)
    query = UserFilterCustomOrderBy(custom_order_by=order_by).sort(query)
    result = await session.execute(query)
    previous_user = None
    for user in result.scalars().unique().all():
        if not previous_user:
            previous_user = user
            continue
        assert assert_function(previous_user, user)
        previous_user = user


@pytest.mark.parametrize(
    "order_by",
    [
        ["age", "name"],
        ["name"],
        ["created_at", "name"],
    ],
)
def test_restricted_order_by_failure(User, UserFilterRestrictedOrderBy, order_by):
    with pytest.raises(ValidationError):
        UserFilterRestrictedOrderBy(order_by=order_by)


@pytest.mark.parametrize(
    "order_by",
    [
        None,
        [],
        ["-created_at"],
        ["created_at", "+age"],
    ],
)
def test_restricted_order_by_success(User, UserFilterRestrictedOrderBy, order_by):
    assert UserFilterRestrictedOrderBy(order_by=order_by)


@pytest.mark.parametrize(
    "order_by,assert_function",
    [
        [None, lambda previous_user, user: True],
        ["", lambda previous_user, user: True],
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
            "age,-created_at",
            lambda previous_user, user: (previous_user["age"] < user["age"])
            or (previous_user["age"] == user["age"] and previous_user["created_at"] >= user["created_at"]),
        ],
    ],
)
@pytest.mark.asyncio
async def test_api_order_by(test_client, users, order_by, assert_function):
    endpoint = "/users_with_order_by"
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
async def test_api_order_by_invalid_field(test_client, session):
    endpoint = "/users_with_order_by?order_by=invalid"
    response = await test_client.get(endpoint)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_api_no_order_by(test_client, session):
    endpoint = "/users_with_no_order_by?order_by=age"
    with pytest.raises(
        AttributeError, match="Ordering field order_by is not defined. Make sure to add it to your filter class."
    ):
        await test_client.get(endpoint)


@pytest.mark.parametrize(
    "order_by,assert_function,status_code",
    [
        [None, lambda previous_user, user: True, status.HTTP_200_OK],
        ["", lambda previous_user, user: True, status.HTTP_200_OK],
        ["name", None, status.HTTP_422_UNPROCESSABLE_ENTITY],
        ["age,-name", None, status.HTTP_422_UNPROCESSABLE_ENTITY],
        ["-age", lambda previous_user, user: previous_user["age"] >= user["age"], status.HTTP_200_OK],
        [
            "age,-created_at",
            lambda previous_user, user: (previous_user["age"] < user["age"])
            or (previous_user["age"] == user["age"] and previous_user["created_at"] >= user["created_at"]),
            status.HTTP_200_OK,
        ],
    ],
)
@pytest.mark.asyncio
async def test_api_restricted_order_by(test_client, users, order_by, assert_function, status_code):
    endpoint = "/users_with_restricted_order_by"
    if order_by is not None:
        endpoint = f"{endpoint}?order_by={order_by}"
    response = await test_client.get(endpoint)
    assert response.status_code == status_code
    if status_code == status.HTTP_200_OK:
        previous_user = None
        for user in response.json():
            if not previous_user:
                previous_user = user
                continue
            assert assert_function(previous_user, user)
            previous_user = user


@pytest.mark.asyncio
async def test_api_custom_order_by(test_client, session):
    endpoint = "/users_with_custom_order_by?custom_order_by=age"
    response = await test_client.get(endpoint)
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.parametrize(
    "order_by, ambiguous_field_names",
    [
        (["age", "age"], "age, age."),
        (["-age", "age"], "-age, age."),
        (["name", "-age", "-name", "name"], "name, -name, name"),
        (["name", "-age", "name", "age"], "-age, age, name, name"),
    ],
)
def test_order_by_with_duplicates_fail(UserFilterOrderBy, order_by, ambiguous_field_names):
    with pytest.raises(ValidationError, match=f"The following was ambiguous: {ambiguous_field_names}."):
        UserFilterOrderBy(order_by=order_by)
