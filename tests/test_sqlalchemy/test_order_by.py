import pytest
from pydantic import ValidationError
from sqlalchemy import select

from fastapi_filter.contrib.sqlalchemy import OrderBy


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
def test_basic_orm_order_by(session, User, users, order_by, assert_function):
    class UserOrderBy(OrderBy):
        class Constants:
            model = User

    query = select(User)
    query = UserOrderBy(order_by=order_by).sort(query)
    result = session.execute(query).scalars().all()
    previous_user = None
    for user in result:
        if not previous_user:
            previous_user = user
            continue
        assert assert_function(previous_user, user)
        previous_user = user


def test_orm_order_by_with_default(session, User, users):
    class UserOrderBy(OrderBy):
        class Constants:
            model = User

        order_by: str = "age"

    query = select(User)
    query = UserOrderBy().sort(query)
    previous_user = None
    for user in session.execute(query).scalars().all():
        if not previous_user:
            previous_user = user
            continue
        assert previous_user.age <= user.age
        previous_user = user


def test_invalid_orm_order_by(User, users):
    class UserOrderBy(OrderBy):
        class Constants:
            model = User

    with pytest.raises(ValidationError):
        UserOrderBy(order_by="invalid")
