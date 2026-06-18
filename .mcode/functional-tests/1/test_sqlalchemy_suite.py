"""Functional tests for the fastapi-filter library's SQLAlchemy backend.

These tests wrap the library's own pytest suite and verify:
1. FilterDepends (existing pattern) still works - regression test for _FilterWrapper refactor
2. Annotated[Filter, Query()] native pattern works - new feature in the modernization
3. split_str validator handles comma-separated strings in both FilterDepends and native paths
4. Order-by functionality works correctly

This is a CLI-style functional test: each test class invokes the library's pytest suite
with a specific subset of tests via subprocess and checks the exit code + output.
"""

import os
import shutil
import subprocess

_uv = shutil.which("uv")
if _uv is None:
    raise RuntimeError("uv binary not found on PATH; install uv before running functional tests")
UV_BIN: str = _uv
REPO_DIR: str = os.path.join(os.environ.get("WORKSPACE_DIR", "/l2l/workspace"), "fastapi-filter")
ENV = {**os.environ}


def run_pytest(test_selector: str, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    """Run a specific subset of the SQLAlchemy test suite via uv run pytest."""
    cmd = [
        UV_BIN,
        "run",
        "pytest",
        f"tests/test_sqlalchemy/{test_selector}",
        "-v",
        "--no-header",
        "--tb=short",
        "--no-cov",  # disable coverage for functional test runs
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
        timeout=120,
        env=ENV,
    )


def assert_pytest_passed(result: subprocess.CompletedProcess, label: str) -> None:
    """Assert that a subprocess pytest run succeeded and reported passing tests."""
    assert result.returncode == 0, (
        f"{label} failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "passed" in result.stdout


class TestFilterDependsRegression:
    """Regression tests for the FilterDepends pattern after _FilterWrapper refactor.

    These tests verify the existing FilterDepends functionality is preserved.
    test_filter.py::test_filter covers all the filter operators via direct instantiation.
    """

    def test_filter_direct_instantiation(self):
        """FilterDepends pattern: direct filter instantiation with all operators."""
        result = run_pytest("test_filter.py::test_filter")
        assert_pytest_passed(result, "test_filter")

    def test_filter_api_filterdepends(self):
        """FilterDepends pattern: API endpoint filters via /users and /users-by-alias."""
        result = run_pytest("test_filter.py::test_api")
        assert_pytest_passed(result, "test_api (FilterDepends path)")

    def test_required_filter_validation(self):
        """FilterDepends pattern: required filter fields trigger 422 when missing."""
        result = run_pytest("test_filter.py::test_required_filter")
        assert_pytest_passed(result, "test_required_filter")

    def test_deprecation_like_ilike(self):
        """FilterDepends pattern: like/ilike without % triggers DeprecationWarning."""
        result = run_pytest("test_filter.py::test_filter_deprecation_like_and_ilike")
        assert_pytest_passed(result, "test_filter_deprecation_like_and_ilike")


class TestNativeAnnotatedPattern:
    """Tests for the new Annotated[Filter, Query()] native pattern.

    This is a new feature added in the modernization (target_only).
    The /users-native endpoint uses Annotated[FlatUserFilter, Query()]
    and must support comma-separated string handling via split_str.
    """

    def test_native_pattern_basic_filters(self):
        """Native Annotated[Filter, Query()] pattern: basic name and age filters."""
        result = run_pytest(
            "test_filter.py::test_api_native_pattern",
            extra_args=["-k", "filter_0 or filter_2 or filter_3 or filter_5 or filter_6"],
        )
        assert_pytest_passed(result, "test_api_native_pattern (basic filters)")

    def test_native_pattern_split_str_comma_handling(self):
        """Native pattern: split_str handles single-element list wrapping from FastAPI.

        When FastAPI receives ?name__in=Mr+Praline,Mr+Creosote via native Annotated[Filter, Query()],
        it wraps the value in a list: ["Mr Praline,Mr Creosote"].
        The split_str validator must detect this and split on commas.
        This verifies the split_str fix that handles the single-element list wrapping
        from FastAPI's native Annotated[Filter, Query()] path.

        The test_api_native_pattern parametrize includes cases like:
          filter_1: {"name__in": "Mr Praline,Mr Creosote,Gumbys,Knight"} -> 3 results
          filter_4: {"name__not_in": "Mr Praline,Mr Creosote,Gumbys,Knight"} -> 2 results
          filter_7: {"age__in": "1"} -> 1 result
          filter_8: {"age__in": "21,33"} -> 3 results
        """
        result = run_pytest(
            "test_filter.py::test_api_native_pattern",
            extra_args=["-k", "filter_1 or filter_4 or filter_7 or filter_8"],
        )
        assert_pytest_passed(result, "split_str comma handling in native pattern")
        # Verify parametrized cases with comma-separated string values pass
        # These are filter_1 (name__in), filter_4 (name__not_in), filter_7/8 (age__in)
        assert "filter_1" in result.stdout
        assert "filter_4" in result.stdout
        assert "filter_7" in result.stdout
        assert "filter_8" in result.stdout


class TestOrderByFunctionality:
    """Tests for the order_by sorting functionality.

    These cover the full order_by test suite including direction (+/-),
    custom ordering fields, restricted ordering, and duplicate detection.
    """

    def test_order_by_direct(self):
        """Direct order_by instantiation with various sort directions."""
        result = run_pytest("test_order_by.py::test_order_by")
        assert_pytest_passed(result, "test_order_by")

    def test_order_by_with_default(self):
        """Order-by with a default value is applied when no order_by param is given."""
        result = run_pytest("test_order_by.py::test_order_by_with_default")
        assert_pytest_passed(result, "test_order_by_with_default")

    def test_order_by_api_with_default(self):
        """API endpoint: order_by with default applied correctly via HTTP."""
        result = run_pytest("test_order_by.py::test_api_order_by_with_default")
        assert_pytest_passed(result, "test_api_order_by_with_default")

    def test_invalid_order_by(self):
        """Invalid order_by field raises ValidationError."""
        result = run_pytest("test_order_by.py::test_invalid_order_by")
        assert_pytest_passed(result, "test_invalid_order_by")

    def test_missing_order_by_field(self):
        """Using sort() on a filter without order_by defined raises AttributeError."""
        result = run_pytest("test_order_by.py::test_missing_order_by_field")
        assert_pytest_passed(result, "test_missing_order_by_field")

    def test_custom_order_by(self):
        """Custom ordering_field_name (not default 'order_by') works correctly."""
        result = run_pytest("test_order_by.py::test_custom_order_by")
        assert_pytest_passed(result, "test_custom_order_by")

    def test_restricted_order_by_failure(self):
        """Order_by with non-allowed field raises ValidationError."""
        result = run_pytest("test_order_by.py::test_restricted_order_by_failure")
        assert_pytest_passed(result, "test_restricted_order_by_failure")

    def test_restricted_order_by_success(self):
        """Order_by with allowed fields succeeds."""
        result = run_pytest("test_order_by.py::test_restricted_order_by_success")
        assert_pytest_passed(result, "test_restricted_order_by_success")

    def test_api_order_by(self):
        """API endpoint: order_by via HTTP query params works correctly."""
        result = run_pytest("test_order_by.py::test_api_order_by")
        assert_pytest_passed(result, "test_api_order_by")

    def test_api_order_by_invalid_field(self):
        """API endpoint: invalid order_by field returns 422."""
        result = run_pytest("test_order_by.py::test_api_order_by_invalid_field")
        assert_pytest_passed(result, "test_api_order_by_invalid_field")

    def test_api_restricted_order_by(self):
        """API endpoint: restricted order_by fields enforce allowlist."""
        result = run_pytest("test_order_by.py::test_api_restricted_order_by")
        assert_pytest_passed(result, "test_api_restricted_order_by")

    def test_api_custom_order_by(self):
        """API endpoint: custom ordering_field_name used via HTTP."""
        result = run_pytest("test_order_by.py::test_api_custom_order_by")
        assert_pytest_passed(result, "test_api_custom_order_by")

    def test_order_by_duplicates_fail(self):
        """Duplicate fields in order_by raise ValidationError with descriptive message."""
        result = run_pytest("test_order_by.py::test_order_by_with_duplicates_fail")
        assert_pytest_passed(result, "test_order_by_with_duplicates_fail")
