import pytest
from pydantic import ValidationError

from fastapi_filter.contrib.mongoengine import Filter


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
def test_basic_order_by(User, users, order_by, assert_function):
    class UserFilter(Filter):
        class Constants(Filter.Constants):
            model = User

        order_by: list[str] | None

    query = User.objects().all()
    query = UserFilter(order_by=order_by).sort(query)
    previous_user = None
    for user in query:
        if not previous_user:
            previous_user = user
            continue
        assert assert_function(previous_user, user)
        previous_user = user


def test_order_by_with_default(User, users):
    class UserFilter(Filter):
        class Constants(Filter.Constants):
            model = User

        order_by: list[str] = ["age"]

    query = User.objects().all()
    query = UserFilter().sort(query)
    previous_user = None
    for user in query:
        if not previous_user:
            previous_user = user
            continue
        assert previous_user.age <= user.age
        previous_user = user


def test_invalid_order_by(User, users):
    class UserFilter(Filter):
        class Constants(Filter.Constants):
            model = User

        order_by: list[str] | None

    with pytest.raises(ValidationError):
        UserFilter(order_by="invalid")


def test_missing_order_by_field(User):
    class UserFilter(Filter):
        class Constants(Filter.Constants):
            model = User

    query = User.objects().all()

    with pytest.raises(AttributeError):
        UserFilter().sort(query)
