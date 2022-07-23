import pytest
from pydantic import ValidationError
from sqlalchemy import select


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
async def test_api_basic_order_by(test_client, users, order_by, assert_function):
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


@pytest.mark.parametrize(
    "order_by,assert_function",
    [
        [None, lambda previous_user, user: True],
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
    for user in result.scalars().all():
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
        ["id"],
        ["id", "age"],
    ],
)
def test_restricted_order_by_success(User, UserFilterRestrictedOrderBy, order_by):
    assert UserFilterRestrictedOrderBy(order_by=order_by)
