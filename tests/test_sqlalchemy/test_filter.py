from urllib.parse import urlencode

import pytest
from fastapi import status
from sqlalchemy.future import select


@pytest.mark.parametrize(
    "filter_,expected_count",
    [
        [{"name": "Mr Praline"}, 1],
        [{"name__neq": "Mr Praline"}, 4],
        [{"name__in": "Mr Praline,Mr Creosote,Gumbys,Knight"}, 3],
        [{"name__like": "Mr"}, 2],
        [{"name__ilike": "mr"}, 2],
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
@pytest.mark.asyncio
async def test_filter(session, Address, User, UserFilter, users, filter_, expected_count):
    query = select(User).outerjoin(Address)
    query = UserFilter(**filter_).filter(query)
    result = await session.execute(query)
    assert len(result.scalars().unique().all()) == expected_count


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
@pytest.mark.asyncio
async def test_api(test_client, users, filter_, expected_count):
    response = await test_client.get(f"/users?{urlencode(filter_)}")
    assert len(response.json()) == expected_count


@pytest.mark.parametrize(
    "filter_,expected_status_code",
    [
        [{"is_individual": True}, status.HTTP_200_OK],
        [{"is_individual": False}, status.HTTP_200_OK],
        [{}, status.HTTP_422_UNPROCESSABLE_ENTITY],
        [{"is_individual": None}, status.HTTP_422_UNPROCESSABLE_ENTITY],
    ],
)
@pytest.mark.asyncio
async def test_required_filter(test_client, sports, filter_, expected_status_code):
    response = await test_client.get(f"/sports?{urlencode(filter_)}")
    assert response.status_code == expected_status_code
