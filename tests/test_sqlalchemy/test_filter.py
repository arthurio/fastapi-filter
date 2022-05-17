from typing import Optional

import pytest
from sqlalchemy.future import select

from fastapi_filter.contrib.sqlalchemy import Filter


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
    ],
)
def test_basic_filter(session, User, users, filter_, expected_count):
    class UserFilter(Filter):
        name: Optional[str]
        name__in: Optional[list[str]]
        name__not: Optional[str]
        name__not_in: Optional[list[str]]
        name__isnull: Optional[bool]
        age: Optional[int]
        age__lt: Optional[int]
        age__lte: Optional[int]
        age__gt: Optional[int]
        age__gte: Optional[int]
        age__in: Optional[list[int]]

        class Constants:
            model = User

    query = select(User)
    query = UserFilter(**filter_).filter(query)
    result = session.execute(query).scalars().all()
    assert len(result) == expected_count
