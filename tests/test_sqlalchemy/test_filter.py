import pytest
from sqlalchemy.future import select

from fastapi_filter import FilterDepends, nested_filter
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
        [{"address": {"country__not_in": "France"}}, 3],
        [{"address": {"street__isnull": True}}, 2],
        [{"address": {"city__in": "Nantes,Denver"}}, 3],
        [{"address": {"city": "San Francisco"}}, 1],
        [{"address_id__isnull": True}, 1],
    ],
)
async def test_basic_filter(session, Address, User, users, filter_, expected_count):
    class AddressFilter(Filter):
        street__isnull: bool | None
        city: str | None
        city__in: list[str] | None
        country__not_in: list[str] | None

        class Constants:
            model = Address

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
        address: AddressFilter | None = FilterDepends(nested_filter("address", AddressFilter))
        address_id__isnull: bool | None

        class Constants:
            model = User

    query = select(User).outerjoin(Address).distinct()
    query = UserFilter(**filter_).filter(query)

    result = await session.execute(query)
    assert len(result.scalars().all()) == expected_count
