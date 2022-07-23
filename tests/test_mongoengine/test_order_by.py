import pytest
from pydantic import ValidationError


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
def test_basic_order_by(User, users, UserFilterOrderBy, order_by, assert_function):
    query = User.objects().all()
    query = UserFilterOrderBy(order_by=order_by).sort(query)
    previous_user = None
    for user in query:
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


def test_order_by_with_default(User, users, UserFilterOrderByWithDefault):
    query = User.objects().all()
    query = UserFilterOrderByWithDefault().sort(query)
    previous_user = None
    for user in query:
        if not previous_user:
            previous_user = user
            continue
        assert previous_user.age <= user.age
        previous_user = user


def test_invalid_order_by(User, users, UserFilterOrderBy):
    with pytest.raises(ValidationError):
        UserFilterOrderBy(order_by="invalid")


def test_missing_order_by_field(User, UserFilterNoOrderBy):
    query = User.objects().all()

    with pytest.raises(AttributeError):
        UserFilterNoOrderBy().sort(query)
