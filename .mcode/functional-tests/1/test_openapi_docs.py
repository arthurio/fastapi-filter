"""Functional tests for OpenAPI spec and docs endpoints.

Tests verify that /openapi.json returns a valid spec and /docs serves
the Swagger UI documentation page.
"""

import requests
import pytest

BASE_URL = "http://127.0.0.1:8000"


@pytest.fixture(autouse=True)
def health_check():
    """Confirm the app is reachable before running tests."""
    resp = requests.get(f"{BASE_URL}/docs", timeout=5)
    assert resp.status_code == 200


class TestOpenAPISpec:
    """GET /openapi.json -- OpenAPI specification."""

    def test_openapi_returns_200(self):
        """GET /openapi.json returns 200 with JSON content."""
        resp = requests.get(f"{BASE_URL}/openapi.json", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "openapi" in data
        assert "paths" in data

    def test_openapi_has_users_path(self):
        """The OpenAPI spec includes the /users endpoint."""
        resp = requests.get(f"{BASE_URL}/openapi.json", timeout=10)
        data = resp.json()
        assert "/users" in data["paths"]
        assert "get" in data["paths"]["/users"]

    def test_openapi_has_addresses_path(self):
        """The OpenAPI spec includes the /addresses endpoint."""
        resp = requests.get(f"{BASE_URL}/openapi.json", timeout=10)
        data = resp.json()
        assert "/addresses" in data["paths"]
        assert "get" in data["paths"]["/addresses"]

    def test_openapi_users_age_gte_required(self):
        """The OpenAPI spec marks age__gte as required on /users."""
        resp = requests.get(f"{BASE_URL}/openapi.json", timeout=10)
        data = resp.json()
        params = data["paths"]["/users"]["get"]["parameters"]
        age_gte_params = [p for p in params if p["name"] == "age__gte"]
        assert len(age_gte_params) == 1
        assert age_gte_params[0]["required"] is True

    def test_openapi_has_schemas(self):
        """The OpenAPI spec includes UserOut and AddressOut schemas."""
        resp = requests.get(f"{BASE_URL}/openapi.json", timeout=10)
        data = resp.json()
        schemas = data.get("components", {}).get("schemas", {})
        assert "UserOut" in schemas
        assert "AddressOut" in schemas


class TestDocsEndpoint:
    """GET /docs -- Swagger UI."""

    def test_docs_returns_200(self):
        """GET /docs returns 200."""
        resp = requests.get(f"{BASE_URL}/docs", timeout=10)
        assert resp.status_code == 200

    def test_docs_returns_html(self):
        """GET /docs returns HTML content."""
        resp = requests.get(f"{BASE_URL}/docs", timeout=10)
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "text/html" in content_type
