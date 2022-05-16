from typing import Optional

import pytest

from fastapi_filter.contrib.mongoengine import Filter


@pytest.mark.parametrize(
    "filter_,expected_count",
    [
        [{"name": "Arthur"}, 1],
        [{"name__isnull": True}, 1],
        [{"name__nin": "Arthur,Christina,Akash,Matt"}, 3],
        [{"name__isnull": False}, 5],
        [{"name__ne": "Arthur"}, 5],
        [{"name__ne": "Arthur", "age__gte": 21, "age__lt": 50}, 2],
        [{"age__in": [1]}, 1],
        [{"age__in": "1"}, 1],
        [{"age__in": "21,33"}, 3],
    ],
)
def test_basic_filter(User, users, filter_, expected_count):
    class UserFilter(Filter):
        name: Optional[str]
        name__in: Optional[list[str]]
        name__not: Optional[str]
        name__nin: Optional[list[str]]
        name__ne: Optional[str]
        name__isnull: Optional[bool]
        age: Optional[int]
        age__lt: Optional[int]
        age__lte: Optional[int]
        age__gt: Optional[int]
        age__gte: Optional[int]
        age__in: Optional[list[int]]

    query = User.objects().all()
    query = UserFilter(**filter_).filter(query)
    assert query.count() == expected_count
