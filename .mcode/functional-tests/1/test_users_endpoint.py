"""Functional tests for GET /users endpoint.

Tests cover happy path, filtering operators (gte, lt, like, ilike, neq),
ordering, search, required parameter enforcement, nested address filtering,
and response structure validation.

The app seeds 100 random users with Faker, so tests must not depend on
specific values -- they validate structure, counts, and filter correctness.
"""

import requests
import pytest

BASE_URL = "http://127.0.0.1:8000"


@pytest.fixture(autouse=True)
def health_check():
    """Confirm the app is reachable before running tests."""
    resp = requests.get(f"{BASE_URL}/docs", timeout=5)
    assert resp.status_code == 200


class TestUsersHappyPath:
    """GET /users -- basic happy path tests."""

    def test_get_users_returns_200(self):
        """GET /users with required age__gte returns 200 and a list."""
        resp = requests.get(f"{BASE_URL}/users", params={"age__gte": 0}, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 100  # app seeds exactly 100 users

    def test_user_response_structure(self):
        """Each user object has the expected fields and types."""
        resp = requests.get(f"{BASE_URL}/users", params={"age__gte": 0}, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        user = data[0]
        assert "id" in user
        assert "name" in user
        assert "email" in user
        assert "age" in user
        assert "address" in user
        assert isinstance(user["id"], int)
        assert isinstance(user["name"], str)
        assert isinstance(user["email"], str)
        assert isinstance(user["age"], int)

    def test_user_address_structure(self):
        """Each user's address has the expected fields."""
        resp = requests.get(f"{BASE_URL}/users", params={"age__gte": 0}, timeout=10)
        data = resp.json()
        # Find a user with a non-null address
        users_with_address = [u for u in data if u.get("address") is not None]
        assert len(users_with_address) > 0, "Expected at least one user with an address"
        addr = users_with_address[0]["address"]
        assert "id" in addr
        assert "street" in addr
        assert "city" in addr
        assert "country" in addr
        assert isinstance(addr["id"], int)
        assert isinstance(addr["street"], str)
        assert isinstance(addr["city"], str)
        assert isinstance(addr["country"], str)


class TestUsersRequiredParams:
    """GET /users -- required parameter enforcement."""

    def test_missing_age_gte_returns_422(self):
        """age__gte is required; omitting it returns 422."""
        resp = requests.get(f"{BASE_URL}/users", timeout=10)
        assert resp.status_code == 422
        body = resp.json()
        assert "detail" in body
        # Verify the error mentions the missing field
        locs = [str(e.get("loc", [])) for e in body["detail"]]
        assert any("age__gte" in loc for loc in locs)


class TestUsersAgeFiltering:
    """GET /users -- age filtering operators."""

    def test_age_gte_filters_correctly(self):
        """age__gte=100 returns only users with age >= 100."""
        resp = requests.get(f"{BASE_URL}/users", params={"age__gte": 100}, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        for user in data:
            assert user["age"] >= 100, f"User {user['name']} has age {user['age']} < 100"

    def test_age_lt_filters_correctly(self):
        """age__lt=20 combined with age__gte=0 returns only users with age < 20."""
        resp = requests.get(
            f"{BASE_URL}/users", params={"age__gte": 0, "age__lt": 20}, timeout=10
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0, "Expected at least one user with age < 20"
        for user in data:
            assert user["age"] < 20, f"User {user['name']} has age {user['age']} >= 20"
            assert user["age"] >= 0

    def test_age_gte_high_value_returns_empty(self):
        """age__gte=999 returns empty list (no one that old)."""
        resp = requests.get(f"{BASE_URL}/users", params={"age__gte": 999}, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data == []

    def test_age_range_combination(self):
        """Combining age__gte and age__lt creates a range filter."""
        resp = requests.get(
            f"{BASE_URL}/users", params={"age__gte": 50, "age__lt": 60}, timeout=10
        )
        assert resp.status_code == 200
        data = resp.json()
        for user in data:
            assert 50 <= user["age"] < 60


class TestUsersNameFiltering:
    """GET /users -- name filtering operators."""

    def test_name_exact_match(self):
        """name= exact match returns matching users only."""
        # First get a name that exists
        resp = requests.get(f"{BASE_URL}/users", params={"age__gte": 0}, timeout=10)
        data = resp.json()
        target_name = data[0]["name"]
        # Filter by that exact name
        resp2 = requests.get(
            f"{BASE_URL}/users",
            params={"age__gte": 0, "name": target_name},
            timeout=10,
        )
        assert resp2.status_code == 200
        filtered = resp2.json()
        assert len(filtered) > 0
        for user in filtered:
            assert user["name"] == target_name

    def test_name_like_case_sensitive(self):
        """name__like performs case-sensitive LIKE matching."""
        resp = requests.get(
            f"{BASE_URL}/users",
            params={"age__gte": 0, "name__like": "%a%"},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        # All returned names should contain lowercase 'a'
        for user in data:
            assert "a" in user["name"], f"Name '{user['name']}' does not contain 'a'"

    def test_name_ilike_case_insensitive(self):
        """name__ilike performs case-insensitive LIKE matching."""
        resp_like = requests.get(
            f"{BASE_URL}/users",
            params={"age__gte": 0, "name__like": "%a%"},
            timeout=10,
        )
        resp_ilike = requests.get(
            f"{BASE_URL}/users",
            params={"age__gte": 0, "name__ilike": "%a%"},
            timeout=10,
        )
        assert resp_like.status_code == 200
        assert resp_ilike.status_code == 200
        # ilike should return >= as many results as like (case insensitive matches more)
        assert len(resp_ilike.json()) >= len(resp_like.json())

    def test_name_neq_excludes(self):
        """name__neq excludes the specified name."""
        resp_all = requests.get(
            f"{BASE_URL}/users", params={"age__gte": 0}, timeout=10
        )
        all_users = resp_all.json()
        target_name = all_users[0]["name"]
        resp_neq = requests.get(
            f"{BASE_URL}/users",
            params={"age__gte": 0, "name__neq": target_name},
            timeout=10,
        )
        assert resp_neq.status_code == 200
        neq_users = resp_neq.json()
        for user in neq_users:
            assert user["name"] != target_name
        # Count should be less by the number of users with that name
        matching = [u for u in all_users if u["name"] == target_name]
        assert len(neq_users) == len(all_users) - len(matching)


class TestUsersOrdering:
    """GET /users -- ordering behavior."""

    def test_default_order_by_age(self):
        """Default order is by age ascending."""
        resp = requests.get(f"{BASE_URL}/users", params={"age__gte": 0}, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        ages = [u["age"] for u in data]
        assert ages == sorted(ages), "Default ordering should be by age ascending"

    def test_order_by_age_descending(self):
        """order_by=-age returns users in descending age order."""
        resp = requests.get(
            f"{BASE_URL}/users",
            params={"age__gte": 0, "order_by": "-age"},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        ages = [u["age"] for u in data]
        assert ages == sorted(ages, reverse=True), "Should be sorted by age descending"

    def test_order_by_name(self):
        """order_by=name returns users sorted by name ascending."""
        resp = requests.get(
            f"{BASE_URL}/users",
            params={"age__gte": 0, "order_by": "name"},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        names = [u["name"] for u in data]
        assert names == sorted(names), "Should be sorted by name ascending"

    def test_order_by_invalid_field_returns_422(self):
        """Ordering by an invalid field returns 422."""
        resp = requests.get(
            f"{BASE_URL}/users",
            params={"age__gte": 0, "order_by": "invalid_field"},
            timeout=10,
        )
        assert resp.status_code == 422


class TestUsersSearch:
    """GET /users -- search functionality."""

    def test_search_filters_by_name(self):
        """search parameter filters users by name (partial match)."""
        # First get a name
        resp = requests.get(f"{BASE_URL}/users", params={"age__gte": 0}, timeout=10)
        all_users = resp.json()
        # Pick a last name from the first user
        target_name = all_users[0]["name"].split()[-1]
        resp_search = requests.get(
            f"{BASE_URL}/users",
            params={"age__gte": 0, "search": target_name},
            timeout=10,
        )
        assert resp_search.status_code == 200
        results = resp_search.json()
        assert len(results) > 0
        # All results should contain the search term in their name (case insensitive)
        for user in results:
            assert target_name.lower() in user["name"].lower()

    def test_search_no_results(self):
        """search with a non-matching term returns empty list."""
        resp = requests.get(
            f"{BASE_URL}/users",
            params={"age__gte": 0, "search": "ZZZZNONEXISTENT99999"},
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestUsersAddressFiltering:
    """GET /users -- filtering by nested address fields."""

    def test_filter_by_address_country(self):
        """address__country filters users by their address country."""
        # First find a country that exists
        resp = requests.get(f"{BASE_URL}/users", params={"age__gte": 0}, timeout=10)
        all_users = resp.json()
        users_with_addr = [u for u in all_users if u.get("address")]
        assert len(users_with_addr) > 0
        target_country = users_with_addr[0]["address"]["country"]
        # Filter by that country
        resp2 = requests.get(
            f"{BASE_URL}/users",
            params={"age__gte": 0, "address__country": target_country},
            timeout=10,
        )
        assert resp2.status_code == 200
        filtered = resp2.json()
        assert len(filtered) > 0
        for user in filtered:
            assert user["address"]["country"] == target_country

    def test_filter_by_address_city(self):
        """address__city filters users by their address city."""
        resp = requests.get(f"{BASE_URL}/users", params={"age__gte": 0}, timeout=10)
        all_users = resp.json()
        users_with_addr = [u for u in all_users if u.get("address")]
        target_city = users_with_addr[0]["address"]["city"]
        resp2 = requests.get(
            f"{BASE_URL}/users",
            params={"age__gte": 0, "address__city": target_city},
            timeout=10,
        )
        assert resp2.status_code == 200
        filtered = resp2.json()
        assert len(filtered) > 0
        for user in filtered:
            assert user["address"]["city"] == target_city


class TestUsersInvalidInput:
    """GET /users -- invalid input handling."""

    def test_age_gte_non_integer_returns_422(self):
        """age__gte with a non-integer value returns 422."""
        resp = requests.get(
            f"{BASE_URL}/users", params={"age__gte": "abc"}, timeout=10
        )
        assert resp.status_code == 422

    def test_age_lt_non_integer_returns_422(self):
        """age__lt with a non-integer value returns 422."""
        resp = requests.get(
            f"{BASE_URL}/users", params={"age__gte": 0, "age__lt": "xyz"}, timeout=10
        )
        assert resp.status_code == 422
