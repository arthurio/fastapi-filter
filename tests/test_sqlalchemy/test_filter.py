from urllib.parse import urlencode

import pytest
from fastapi import status
from sqlalchemy.future import select


@pytest.mark.parametrize(
    "filter_,expected_count",
    [
        [{"name": "Mr Praline"}, 1],
        [{"name__neq": "Mr Praline"}, 4],
        [{"name__in": ["Mr Praline", "Mr Creosote", "Gumbys", "Knight"]}, 3],
        [{"name__in": "Mr Praline,Mr Creosote,Gumbys,Knight"}, 3],
        [{"name__like": "%Mr%"}, 2],
        [{"name__ilike": "%mr%"}, 2],
        [{"name__like": "%colonel"}, 1],
        [{"name__like": "Mr %"}, 2],
        [{"name__isnull": True}, 1],
        [{"name__isnull": False}, 5],
        [{"name__not_in": ["Mr Praline", "Mr Creosote", "Gumbys", "Knight"]}, 2],
        [{"name__not_in": "Mr Praline,Mr Creosote,Gumbys,Knight"}, 2],
        [{"name__not": "Mr Praline"}, 5],
        [{"name__not": "Mr Praline", "age__gte": 21, "age__lt": 50}, 2],
        [{"age__in": [1]}, 1],
        [{"age__in": [21, 33]}, 3],
        [{"address": {"country__not_in": ["France"]}}, 3],
        [{"age__in": "1"}, 1],
        [{"age__in": "21,33"}, 3],
        [{"address": {"country__not_in": "France"}}, 3],
        [{"address": {"street__isnull": True}}, 2],
        [{"address": {"city__in": ["Nantes", "Denver"]}}, 3],
        [{"address": {"city__in": "Nantes,Denver"}}, 3],
        [{"address": {"city": "San Francisco"}}, 1],
        [{"address_id__isnull": True}, 1],
        [{"search": "Mr"}, 2],
        [{"search": "mr"}, 2],
        [{"is_not_active": True}, 2],
        [{"is_not_active": False}, 4],
        [{"is_not_active": None}, 6],
    ],
)
@pytest.mark.usefixtures("users")
@pytest.mark.asyncio
async def test_filter(session, Address, User, UserFilter, filter_, expected_count):
    query = select(User).outerjoin(Address)
    user_filter = UserFilter(**filter_)

    if user_filter.is_not_active is not None:
        query = query.filter(User.is_active.is_(not user_filter.is_not_active))

    query = user_filter.filter(query)
    result = await session.execute(query)
    assert len(result.scalars().unique().all()) == expected_count


@pytest.mark.parametrize(
    "filter_,expected_count",
    [
        [{"name__like": "Mr"}, 2],
        [{"name__ilike": "mr"}, 2],
    ],
)
@pytest.mark.usefixtures("users")
@pytest.mark.asyncio
async def test_filter_deprecation_like_and_ilike(session, Address, User, UserFilter, filter_, expected_count):
    query = select(User).outerjoin(Address)
    with pytest.warns(DeprecationWarning, match="like and ilike operators."):
        query = UserFilter(**filter_).filter(query)
    result = await session.execute(query)
    assert len(result.scalars().unique().all()) == expected_count


@pytest.mark.parametrize("uri", ["/users", "/users-by-alias"])
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
        [{"address__country__not_in": "France"}, 3],
        [{"address__street__isnull": True}, 2],
        [{"address__city__in": "Nantes,Denver"}, 3],
        [{"address__city": "San Francisco"}, 1],
        [{"address_id__isnull": True}, 1],
    ],
)
@pytest.mark.usefixtures("users")
@pytest.mark.asyncio
async def test_api(test_client, uri, filter_, expected_count):
    response = await test_client.get(f"{uri}?{urlencode(filter_)}")
    assert len(response.json()) == expected_count


@pytest.mark.parametrize(
    "filter_,expected_status_code",
    [
        [{"is_individual": True}, status.HTTP_200_OK],
        [{"is_individual": False}, status.HTTP_200_OK],
        [{}, status.HTTP_422_UNPROCESSABLE_ENTITY],
        [{"is_individual": None}, status.HTTP_422_UNPROCESSABLE_ENTITY],
        [{"is_individual": True, "bogus_filter": "bad"}, status.HTTP_422_UNPROCESSABLE_ENTITY],
    ],
)
@pytest.mark.usefixtures("sports")
@pytest.mark.asyncio
async def test_required_filter(test_client, filter_, expected_status_code):
    response = await test_client.get(f"/sports?{urlencode(filter_)}")
    assert response.status_code == expected_status_code

    if response.is_error:
        error_json = response.json()
        assert "detail" in error_json
        assert isinstance(error_json["detail"], list)


@pytest.mark.usefixtures("users")
@pytest.mark.asyncio
async def test_raise_attribute_error(session, User, UserFilter):
    with pytest.raises(AttributeError, match="type object 'User' has no attribute 'gender'"):
        query = select(User)
        user_filter = UserFilter(gender="M")

        query = user_filter.filter(query)
        await session.execute(query)
