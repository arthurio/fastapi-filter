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


class TestFilterDependsRegression:
    """Regression tests for the FilterDepends pattern after _FilterWrapper refactor.

    These tests verify the existing FilterDepends functionality is preserved.
    test_filter.py::test_filter covers all the filter operators via direct instantiation.
    """

    def test_filter_direct_instantiation(self):
        """FilterDepends pattern: direct filter instantiation with all operators."""
        result = run_pytest("test_filter.py::test_filter")
        assert result.returncode == 0, f"test_filter failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        assert "passed" in result.stdout

    def test_filter_api_filterdepends(self):
        """FilterDepends pattern: API endpoint filters via /users and /users-by-alias."""
        result = run_pytest("test_filter.py::test_api")
        assert result.returncode == 0, (
            f"test_api (FilterDepends path) failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "passed" in result.stdout

    def test_required_filter_validation(self):
        """FilterDepends pattern: required filter fields trigger 422 when missing."""
        result = run_pytest("test_filter.py::test_required_filter")
        assert result.returncode == 0, (
            f"test_required_filter failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "passed" in result.stdout

    def test_deprecation_like_ilike(self):
        """FilterDepends pattern: like/ilike without % triggers DeprecationWarning."""
        result = run_pytest("test_filter.py::test_filter_deprecation_like_and_ilike")
        assert result.returncode == 0, (
            f"test_filter_deprecation_like_and_ilike failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "passed" in result.stdout


class TestNativeAnnotatedPattern:
    """Tests for the new Annotated[Filter, Query()] native pattern.

    This is a new feature added in the modernization (target_only).
    The /users-native endpoint uses Annotated[FlatUserFilter, Query()]
    and must support comma-separated string handling via split_str.
    """

    def test_native_pattern_basic_filters(self):
        """Native Annotated[Filter, Query()] pattern: basic name and age filters."""
        result = run_pytest("test_filter.py::test_api_native_pattern")
        assert result.returncode == 0, (
            f"test_api_native_pattern failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "passed" in result.stdout

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

        Running the full test_api_native_pattern suite verifies these cases pass.
        """
        result = run_pytest("test_filter.py::test_api_native_pattern")
        assert result.returncode == 0, (
            f"split_str comma handling in native pattern failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        # Verify parametrized cases with comma-separated string values pass
        # These are filter_1 (name__in), filter_4 (name__not_in), filter_7/8 (age__in)
        assert "filter_1" in result.stdout
        assert "filter_4" in result.stdout
        assert "filter_7" in result.stdout
        assert "filter_8" in result.stdout
        assert "passed" in result.stdout


class TestOrderByFunctionality:
    """Tests for the order_by sorting functionality.

    These cover the full order_by test suite including direction (+/-),
    custom ordering fields, restricted ordering, and duplicate detection.
    """

    def test_order_by_direct(self):
        """Direct order_by instantiation with various sort directions."""
        result = run_pytest("test_order_by.py::test_order_by")
        assert result.returncode == 0, f"test_order_by failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        assert "passed" in result.stdout

    def test_order_by_with_default(self):
        """Order-by with a default value is applied when no order_by param is given."""
        result = run_pytest("test_order_by.py::test_order_by_with_default")
        assert result.returncode == 0, (
            f"test_order_by_with_default failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "passed" in result.stdout

    def test_order_by_api_with_default(self):
        """API endpoint: order_by with default applied correctly via HTTP."""
        result = run_pytest("test_order_by.py::test_api_order_by_with_default")
        assert result.returncode == 0, (
            f"test_api_order_by_with_default failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "passed" in result.stdout

    def test_invalid_order_by(self):
        """Invalid order_by field raises ValidationError."""
        result = run_pytest("test_order_by.py::test_invalid_order_by")
        assert result.returncode == 0, (
            f"test_invalid_order_by failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "passed" in result.stdout

    def test_missing_order_by_field(self):
        """Using sort() on a filter without order_by defined raises AttributeError."""
        result = run_pytest("test_order_by.py::test_missing_order_by_field")
        assert result.returncode == 0, (
            f"test_missing_order_by_field failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "passed" in result.stdout

    def test_custom_order_by(self):
        """Custom ordering_field_name (not default 'order_by') works correctly."""
        result = run_pytest("test_order_by.py::test_custom_order_by")
        assert result.returncode == 0, (
            f"test_custom_order_by failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "passed" in result.stdout

    def test_restricted_order_by_failure(self):
        """Order_by with non-allowed field raises ValidationError."""
        result = run_pytest("test_order_by.py::test_restricted_order_by_failure")
        assert result.returncode == 0, (
            f"test_restricted_order_by_failure failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "passed" in result.stdout

    def test_restricted_order_by_success(self):
        """Order_by with allowed fields succeeds."""
        result = run_pytest("test_order_by.py::test_restricted_order_by_success")
        assert result.returncode == 0, (
            f"test_restricted_order_by_success failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "passed" in result.stdout

    def test_api_order_by(self):
        """API endpoint: order_by via HTTP query params works correctly."""
        result = run_pytest("test_order_by.py::test_api_order_by")
        assert result.returncode == 0, f"test_api_order_by failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        assert "passed" in result.stdout

    def test_api_order_by_invalid_field(self):
        """API endpoint: invalid order_by field returns 422."""
        result = run_pytest("test_order_by.py::test_api_order_by_invalid_field")
        assert result.returncode == 0, (
            f"test_api_order_by_invalid_field failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "passed" in result.stdout

    def test_api_restricted_order_by(self):
        """API endpoint: restricted order_by fields enforce allowlist."""
        result = run_pytest("test_order_by.py::test_api_restricted_order_by")
        assert result.returncode == 0, (
            f"test_api_restricted_order_by failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "passed" in result.stdout

    def test_api_custom_order_by(self):
        """API endpoint: custom ordering_field_name used via HTTP."""
        result = run_pytest("test_order_by.py::test_api_custom_order_by")
        assert result.returncode == 0, (
            f"test_api_custom_order_by failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "passed" in result.stdout

    def test_order_by_duplicates_fail(self):
        """Duplicate fields in order_by raise ValidationError with descriptive message."""
        result = run_pytest("test_order_by.py::test_order_by_with_duplicates_fail")
        assert result.returncode == 0, (
            f"test_order_by_with_duplicates_fail failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "passed" in result.stdout
