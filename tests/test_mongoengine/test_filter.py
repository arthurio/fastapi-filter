from urllib.parse import urlencode

import pytest


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
    ],
)
def test_basic_filter(User, UserFilter, Address, users, filter_, expected_count):
    query = UserFilter(**filter_).filter(User.objects())
    assert query.count() == expected_count


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
async def test_api(test_client, Address, User, UserFilter, users, filter_, expected_count):
    response = await test_client.get(f"/users?{urlencode(filter_)}")
    assert len(response.json()) == expected_count
