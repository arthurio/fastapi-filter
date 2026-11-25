from collections.abc import Callable, Mapping
from typing import Any

from fastapi_filter.base.filter import BaseFilterModel

_odm_operator_transformer: dict[str, Callable[[str | None], dict[str, Any] | None]] = {
    "neq": lambda value: {"$ne": value},
    "gt": lambda value: {"$gt": value},
    "gte": lambda value: {"$gte": value},
    "in": lambda value: {"$in": value},
    "isnull": lambda value: None if value else {"$ne": None},
    "lt": lambda value: {"$lt": value},
    "lte": lambda value: {"$lte": value},
    "not": lambda value: {"$ne": value},
    "ne": lambda value: {"$ne": value},
    "not_in": lambda value: {"$nin": value},
    "nin": lambda value: {"$nin": value},
    "like": lambda value: {"$regex": f".*{value}.*"},
    "ilike": lambda value: {"$regex": f".*{value}.*", "$options": "i"},
    "exists": lambda value: {"$exists": value},
}


class _ConditionCollector:
    """Stands in for a query to record `find(condition, **options)` calls of nested filters."""

    def __init__(self) -> None:
        self.conditions: list[tuple[Mapping[str, Any], dict[str, Any]]] = []

    def find(self, condition: Mapping[str, Any], **options: Any) -> "_ConditionCollector":
        self.conditions.append((condition, options))
        return self


class Filter(BaseFilterModel):
    """Base filter for beanie related filters.

    Example:
        ```python
        class MyModel:
            id: PrimaryKey()
            name: StringField(null=True)
            count: IntField()
            created_at: DatetimeField()

        class MyModelFilter(Filter):
            id: int | None
            id__in: str | None
            count: int | None
            count__lte: int | None
            created_at__gt: datetime | None
            name__ne: str | None
            name__nin: list[str] | None
            name__isnull: bool | None
        ```
    """

    def _apply_condition(self, query: Any, field_name: str, operator: str | None, value: Any) -> Any:
        if operator is None:
            return query.find({field_name: value})
        return query.find({field_name: _odm_operator_transformer[operator](value)})

    def _apply_search(self, query: Any, search_fields: list[str], value: Any) -> Any:
        search_conditions = [{field: _odm_operator_transformer["ilike"](value)} for field in search_fields]
        return query.find({"$or": search_conditions})

    def _apply_nested(self, query: Any, field_name: str, nested: BaseFilterModel, nesting_depth: int) -> Any:
        query = query.find(
            {field_name: _odm_operator_transformer["neq"](None)},
            fetch_links=True,
            nesting_depth=nesting_depth,
        )
        # Collect the nested conditions (one level deeper) instead of applying them, so they can be prefixed.
        collector = _ConditionCollector()
        nested._filter_fields(collector, nesting_depth + 1)  # noqa: SLF001
        for part, part_options in collector.conditions:
            for sub_field_name, sub_value in part.items():
                query = query.find(
                    {f"{field_name}.{sub_field_name}": sub_value},
                    **{"fetch_links": True, "nesting_depth": nesting_depth, **part_options},
                )
        return query

    def _finalize_filter(self, query: Any) -> Any:
        return query.find(fetch_links=True)

    def _apply_order(self, query: Any, ordering: list[tuple[str, bool]]) -> Any:
        return query.sort(*self._prefixed_ordering(ordering))
