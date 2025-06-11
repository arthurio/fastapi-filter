from urllib.parse import urlencode

import mongoengine
import pytest
from fastapi import status


@pytest.mark.parametrize(
    "filter_,expected_count",
    [
        [{"name": "Mr Praline"}, 1],
        [{"name__isnull": True}, 1],
        [{"name__nin": "Mr Praline,Mr Creosote,Gumbys,Knight"}, 3],
        [{"name__isnull": False}, 5],
        [{"name__ne": "Mr Praline"}, 5],
        [{"name__ne": "Mr Praline", "age__gte": 21, "age__lt": 50}, 2],
        [{"age__in": [1]}, 1],
        [{"age__in": "1"}, 1],
        [{"age__in": "21,33"}, 3],
        [{"address": {"country__nin": "France"}}, 3],
        [{"address": {"street__isnull": True}}, 1],
        [{"address": {"city__in": "Nantes,Denver"}}, 3],
        [{"address": {"city": "San Francisco"}}, 1],
        [{"search": "Mr"}, 2],
        [{"search": "mr"}, 2],
        [{"is_not_active": True}, 2],
        [{"is_not_active": False}, 4],
        [{"is_not_active": None}, 6],
    ],
)
@pytest.mark.usefixtures("Address", "users")
def test_basic_filter(User, UserFilter, filter_, expected_count):
    query = User.objects()
    user_filter = UserFilter(**filter_)

    if user_filter.is_not_active is not None:
        query = query.filter(is_active__ne=user_filter.is_not_active)

    query = user_filter.filter(query)
    assert query.count() == expected_count


@pytest.mark.parametrize("uri", ["/users", "/users-by-alias"])
@pytest.mark.parametrize(
    "filter_,expected_count",
    [
        [{"name": "Mr Praline"}, 1],
        [{"name__in": "Mr Praline,Mr Creosote,Gumbys,Knight"}, 3],
        [{"name__isnull": True}, 1],
        [{"name__isnull": False}, 5],
        [{"name__nin": "Mr Praline,Mr Creosote,Gumbys,Knight"}, 3],
        [{"name__ne": "Mr Praline"}, 5],
        [{"name__ne": "Mr Praline", "age__gte": 21, "age__lt": 50}, 2],
        [{"age__in": [1]}, 1],
        [{"age__in": "1"}, 1],
        [{"age__in": "21,33"}, 3],
        [{"address__country__nin": "France"}, 3],
        [{"address__street__isnull": True}, 1],
        [{"address__city__in": "Nantes,Denver"}, 3],
        [{"address__city": "San Francisco"}, 1],
    ],
)
@pytest.mark.asyncio
@pytest.mark.usefixtures("Address", "users", "User", "UserFilter")
async def test_api(test_client, uri, filter_, expected_count):
    response = await test_client.get(f"{uri}?{urlencode(filter_)}")
    assert len(response.json()) == expected_count


@pytest.mark.parametrize(
    "filter_,expected_status_code",
    (
        ({"is_individual": True}, status.HTTP_200_OK),
        ({"is_individual": False}, status.HTTP_200_OK),
        ({}, status.HTTP_422_UNPROCESSABLE_ENTITY),
        ({"is_individual": None}, status.HTTP_422_UNPROCESSABLE_ENTITY),
        [{"is_individual": True, "bogus_filter": "bad"}, status.HTTP_422_UNPROCESSABLE_ENTITY],
    ),
)
@pytest.mark.asyncio
async def test_required_filter(test_client, filter_, expected_status_code):
    response = await test_client.get(f"/sports?{urlencode(filter_)}")
    assert response.status_code == expected_status_code

    if response.is_error:
        error_json = response.json()
        assert "detail" in error_json
        assert isinstance(error_json["detail"], list)


@pytest.mark.usefixtures("users")
def test_raise_invalid_query_error(User, UserFilter):
    with pytest.raises(mongoengine.errors.InvalidQueryError, match='Cannot resolve field "gender"'):
        UserFilter(gender="F").filter(User.objects()).count()
