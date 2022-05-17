import pytest
from pydantic import ValidationError

from fastapi_filter.contrib.mongoengine import OrderBy


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
    class UserOrderBy(OrderBy):
        class Constants:
            collection = User

    query = User.objects().all()
    query = UserOrderBy(order_by=order_by).sort(query)
    previous_user = None
    for user in query:
        if not previous_user:
            previous_user = user
            continue
        assert assert_function(previous_user, user)
        previous_user = user


def test_order_by_with_default(User, users):
    class UserOrderBy(OrderBy):
        class Constants:
            collection = User

        order_by: str = "age"

    query = User.objects().all()
    query = UserOrderBy().sort(query)
    previous_user = None
    for user in query:
        if not previous_user:
            previous_user = user
            continue
        assert previous_user.age <= user.age
        previous_user = user


def test_invalid_order_by(User, users):
    class UserOrderBy(OrderBy):
        class Constants:
            collection = User

    with pytest.raises(ValidationError):
        UserOrderBy(order_by="invalid")
