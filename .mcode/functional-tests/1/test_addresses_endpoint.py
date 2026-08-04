"""Functional tests for GET /addresses endpoint.

Tests cover happy path, filtering by street/city/country, city__in filter,
custom ordering, custom search, and response structure validation.

The /addresses endpoint uses a custom prefix 'my_custom_prefix' for all
filter parameters (set via with_prefix in the app code).
"""

import requests
import pytest

BASE_URL = "http://127.0.0.1:8000"


@pytest.fixture(autouse=True)
def health_check():
    """Confirm the app is reachable before running tests."""
    resp = requests.get(f"{BASE_URL}/docs", timeout=5)
    assert resp.status_code == 200


class TestAddressesHappyPath:
    """GET /addresses -- basic happy path tests."""

    def test_get_addresses_returns_200(self):
        """GET /addresses returns 200 and a list of addresses."""
        resp = requests.get(f"{BASE_URL}/addresses", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 100  # app seeds exactly 100 addresses

    def test_address_response_structure(self):
        """Each address object has id, street, city, country."""
        resp = requests.get(f"{BASE_URL}/addresses", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        addr = data[0]
        assert "id" in addr
        assert "street" in addr
        assert "city" in addr
        assert "country" in addr
        assert isinstance(addr["id"], int)
        assert isinstance(addr["street"], str)
        assert isinstance(addr["city"], str)
        assert isinstance(addr["country"], str)


class TestAddressesFiltering:
    """GET /addresses -- filtering by various fields using custom prefix."""

    def test_filter_by_country(self):
        """my_custom_prefix__country filters addresses by exact country match."""
        resp = requests.get(f"{BASE_URL}/addresses", timeout=10)
        all_addrs = resp.json()
        target_country = all_addrs[0]["country"]
        resp2 = requests.get(
            f"{BASE_URL}/addresses",
            params={"my_custom_prefix__country": target_country},
            timeout=10,
        )
        assert resp2.status_code == 200
        filtered = resp2.json()
        assert len(filtered) > 0
        for addr in filtered:
            assert addr["country"] == target_country

    def test_filter_by_city(self):
        """my_custom_prefix__city filters addresses by exact city match."""
        resp = requests.get(f"{BASE_URL}/addresses", timeout=10)
        all_addrs = resp.json()
        target_city = all_addrs[0]["city"]
        resp2 = requests.get(
            f"{BASE_URL}/addresses",
            params={"my_custom_prefix__city": target_city},
            timeout=10,
        )
        assert resp2.status_code == 200
        filtered = resp2.json()
        assert len(filtered) > 0
        for addr in filtered:
            assert addr["city"] == target_city

    def test_filter_by_street(self):
        """my_custom_prefix__street filters addresses by exact street match."""
        resp = requests.get(f"{BASE_URL}/addresses", timeout=10)
        all_addrs = resp.json()
        target_street = all_addrs[0]["street"]
        resp2 = requests.get(
            f"{BASE_URL}/addresses",
            params={"my_custom_prefix__street": target_street},
            timeout=10,
        )
        assert resp2.status_code == 200
        filtered = resp2.json()
        assert len(filtered) > 0
        for addr in filtered:
            assert addr["street"] == target_street

    def test_city_in_filter(self):
        """my_custom_prefix__city__in filters addresses to those in the specified cities."""
        resp = requests.get(f"{BASE_URL}/addresses", timeout=10)
        all_addrs = resp.json()
        city1 = all_addrs[0]["city"]
        city2 = all_addrs[1]["city"] if len(all_addrs) > 1 else city1
        resp2 = requests.get(
            f"{BASE_URL}/addresses",
            params={"my_custom_prefix__city__in": f"{city1},{city2}"},
            timeout=10,
        )
        assert resp2.status_code == 200
        filtered = resp2.json()
        assert len(filtered) > 0
        for addr in filtered:
            assert addr["city"] in [city1, city2]

    def test_filter_nonexistent_country_returns_empty(self):
        """Filtering by a non-existent country returns empty list."""
        resp = requests.get(
            f"{BASE_URL}/addresses",
            params={"my_custom_prefix__country": "ZZNONEXISTENT99"},
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestAddressesOrdering:
    """GET /addresses -- ordering with custom_order_by."""

    def test_order_by_city_ascending(self):
        """custom_order_by=city orders addresses by city ascending."""
        resp = requests.get(
            f"{BASE_URL}/addresses",
            params={"my_custom_prefix__custom_order_by": "city"},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        cities = [a["city"] for a in data]
        assert cities == sorted(cities), "Should be sorted by city ascending"

    def test_order_by_city_descending(self):
        """custom_order_by=-city orders addresses by city descending."""
        resp = requests.get(
            f"{BASE_URL}/addresses",
            params={"my_custom_prefix__custom_order_by": "-city"},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        cities = [a["city"] for a in data]
        assert cities == sorted(cities, reverse=True), "Should be sorted by city descending"

    def test_order_by_country(self):
        """custom_order_by=country orders addresses by country ascending."""
        resp = requests.get(
            f"{BASE_URL}/addresses",
            params={"my_custom_prefix__custom_order_by": "country"},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        countries = [a["country"] for a in data]
        assert countries == sorted(countries), "Should be sorted by country ascending"

    def test_order_by_invalid_field_returns_422(self):
        """Ordering by an invalid field returns 422."""
        resp = requests.get(
            f"{BASE_URL}/addresses",
            params={"my_custom_prefix__custom_order_by": "invalid_field"},
            timeout=10,
        )
        assert resp.status_code == 422


class TestAddressesSearch:
    """GET /addresses -- search functionality."""

    def test_custom_search_finds_matching(self):
        """custom_search searches across street, country, and city fields."""
        resp = requests.get(f"{BASE_URL}/addresses", timeout=10)
        all_addrs = resp.json()
        # Use a substring from the first address city
        target = all_addrs[0]["city"][:4]  # take first 4 chars
        resp2 = requests.get(
            f"{BASE_URL}/addresses",
            params={"my_custom_prefix__custom_search": target},
            timeout=10,
        )
        assert resp2.status_code == 200
        results = resp2.json()
        assert len(results) > 0
        # Each result should contain the search term in at least one searchable field
        for addr in results:
            found = (
                target.lower() in addr["street"].lower()
                or target.lower() in addr["city"].lower()
                or target.lower() in addr["country"].lower()
            )
            assert found, f"Address {addr} does not match search term '{target}'"

    def test_search_no_results(self):
        """Searching for a non-matching term returns empty list."""
        resp = requests.get(
            f"{BASE_URL}/addresses",
            params={"my_custom_prefix__custom_search": "ZZZZNONEXIST99999"},
            timeout=10,
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestAddressesBoundary:
    """GET /addresses -- boundary and edge cases."""

    def test_empty_string_filter(self):
        """Empty string filter value returns valid response."""
        resp = requests.get(
            f"{BASE_URL}/addresses",
            params={"my_custom_prefix__country": ""},
            timeout=10,
        )
        # Should return 200 with results matching empty string (likely none)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
