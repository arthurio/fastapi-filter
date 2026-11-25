from typing import Any

import pytest
from pydantic import ConfigDict

from fastapi_filter import FilterDepends, with_prefix
from fastapi_filter.base.filter import BaseFilterModel


class FakeModel:
    name = "name"
    age = "age"
    city = "city"


class FakeQuery:
    """Records every call made by the template methods."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []


class FakeFilter(BaseFilterModel):
    class Constants(BaseFilterModel.Constants):
        model = FakeModel

    def _apply_condition(self, query, field_name, operator, value):
        query.calls.append(("condition", field_name, operator, value))
        return query

    def _apply_search(self, query, search_fields, value):
        query.calls.append(("search", tuple(search_fields), value))
        return query

    def _apply_nested(self, query, field_name, nested, nesting_depth):
        query.calls.append(("nested", field_name, nesting_depth))
        return super()._apply_nested(query, field_name, nested, nesting_depth)

    def _finalize_filter(self, query):
        query.calls.append(("finalize",))
        return query

    def _apply_order(self, query, ordering):
        query.calls.append(("order", tuple(ordering)))
        return query


class AddressFilter(FakeFilter):
    city: str | None = None
    city__in: list[str] | None = None

    class Constants(FakeFilter.Constants):
        model = FakeModel


class UserFilter(FakeFilter):
    name: str | None = None
    age__gte: int | None = None
    address: AddressFilter | None = None
    order_by: list[str] | None = None
    search: str | None = None

    class Constants(FakeFilter.Constants):
        model = FakeModel
        search_model_fields = ["name", "city"]


def test_constants_defaults():
    constants = BaseFilterModel.Constants
    assert constants.search_model_fields == []
    assert constants.prefix == ""
    assert constants.original_filter is None
    assert constants.ordering_field_name == "order_by"
    assert constants.search_field_name == "search"


def test_constants_subclass_pattern():
    class MyFilter(FakeFilter):
        class Constants(FakeFilter.Constants):
            model = FakeModel
            ordering_field_name = "sort"

    assert MyFilter.Constants.model is FakeModel
    assert MyFilter.Constants.ordering_field_name == "sort"
    assert MyFilter.Constants.search_model_fields == []
    assert MyFilter.Constants.original_filter is None


def test_plain_field_and_operator_splitting():
    query = FakeQuery()
    UserFilter(name="bob", age__gte=3).filter(query)
    assert query.calls == [
        ("condition", "name", None, "bob"),
        ("condition", "age", "gte", 3),
        ("finalize",),
    ]


def test_unset_fields_are_ignored():
    query = FakeQuery()
    UserFilter().filter(query)
    assert query.calls == [("finalize",)]


def test_search_fields():
    query = FakeQuery()
    UserFilter(search="x").filter(query)
    assert query.calls == [("search", ("name", "city"), "x"), ("finalize",)]


def test_search_without_search_model_fields_is_a_regular_field():
    class NoSearch(FakeFilter):
        search: str | None = None

    query = FakeQuery()
    NoSearch(search="x").filter(query)
    assert query.calls == [("condition", "search", None, "x"), ("finalize",)]


def test_custom_search_field_name():
    class Custom(FakeFilter):
        q: str | None = None

        class Constants(FakeFilter.Constants):
            model = FakeModel
            search_field_name = "q"
            search_model_fields = ["name"]

    query = FakeQuery()
    Custom(q="x").filter(query)
    assert query.calls == [("search", ("name",), "x"), ("finalize",)]


def test_nested_filter_is_traversed():
    query = FakeQuery()
    UserFilter(name="bob", address=AddressFilter(city="Paris", city__in=["a", "b"])).filter(query)
    assert query.calls == [
        ("condition", "name", None, "bob"),
        ("nested", "address", 1),
        ("condition", "city", None, "Paris"),
        ("condition", "city", "in", ["a", "b"]),
        ("finalize",),
    ]


def test_empty_nested_filter_is_skipped():
    query = FakeQuery()
    UserFilter(address=AddressFilter()).filter(query)
    assert query.calls == [("finalize",)]


def test_nesting_depth_increases_through_recursion():
    class Inner(FakeFilter):
        city: str | None = None

    class Middle(FakeFilter):
        inner: Inner | None = None

    class Outer(FakeFilter):
        middle: Middle | None = None

    query = FakeQuery()
    Outer(middle=Middle(inner=Inner(city="x"))).filter(query)
    assert query.calls == [
        ("nested", "middle", 1),
        ("nested", "inner", 2),
        ("condition", "city", None, "x"),
        ("finalize",),
    ]


def test_sort_parsing():
    query = FakeQuery()
    UserFilter(order_by=["name", "-age", "+city"]).sort(query)
    assert query.calls == [("order", (("name", False), ("age", True), ("city", False)))]


def test_sort_without_values_returns_query_untouched():
    query = FakeQuery()
    assert UserFilter(order_by=None).sort(query) is query
    assert query.calls == []


def test_order_by_is_not_a_filtering_field():
    query = FakeQuery()
    UserFilter(order_by=["name"]).filter(query)
    assert query.calls == [("finalize",)]


def test_order_by_string_is_split():
    assert UserFilter(order_by="-name, age").order_by == ["-name", "age"]  # type: ignore[arg-type]


def test_invalid_ordering_field():
    with pytest.raises(ValueError, match="nope is not a valid ordering field"):
        UserFilter(order_by=["nope"])


def test_ordering_values_without_field():
    class NoOrdering(FakeFilter):
        name: str | None = None

    with pytest.raises(AttributeError, match="Ordering field order_by is not defined"):
        NoOrdering(name="x").sort(FakeQuery())


def test_hooks_must_be_implemented():
    class Bare(BaseFilterModel):
        name: str | None = None

        class Constants(BaseFilterModel.Constants):
            model = FakeModel

    with pytest.raises(NotImplementedError):
        Bare(name="x").filter(FakeQuery())


def test_search_hook_must_be_implemented():
    class BareSearch(BaseFilterModel):
        search: str | None = None

        class Constants(BaseFilterModel.Constants):
            model = FakeModel
            search_model_fields = ["name"]

    with pytest.raises(NotImplementedError):
        BareSearch(search="x").filter(FakeQuery())


def test_order_hook_must_be_implemented():
    class BareOrder(BaseFilterModel):
        order_by: list[str] | None = None

        class Constants(BaseFilterModel.Constants):
            model = FakeModel

    with pytest.raises(NotImplementedError):
        BareOrder(order_by=["name"]).sort(FakeQuery())


def test_with_prefix_sets_constants_via_class_body():
    prefixed = with_prefix("address", AddressFilter)
    assert prefixed.Constants.prefix == "address"
    assert prefixed.Constants.original_filter is AddressFilter
    assert prefixed.Constants.model is FakeModel
    # the original is untouched
    assert AddressFilter.Constants.prefix == ""
    assert AddressFilter.Constants.original_filter is None
    assert prefixed.model_config == ConfigDict(extra="forbid", alias_generator=prefixed.model_config["alias_generator"])


def test_filter_depends_builds_original_filter_for_prefixed_filter():
    dependency = FilterDepends(with_prefix("address", AddressFilter)).dependency
    result = dependency(address__city="Paris")  # type: ignore[misc]
    assert type(result) is AddressFilter
    assert result.city == "Paris"
