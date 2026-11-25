from enum import Enum
from typing import Any
from warnings import warn

from sqlalchemy import or_
from sqlalchemy.orm import Query
from sqlalchemy.sql.selectable import Select

from ...base.filter import BaseFilterModel


def _backward_compatible_value_for_like_and_ilike(value: str):
    """Add % if not in value to be backward compatible.

    Args:
        value (str): The value to filter.

    Returns:
        Either the unmodified value if a percent sign is present, the value wrapped in % otherwise to preserve
        current behavior.
    """
    if "%" not in value:
        warn(
            "You must pass the % character explicitly to use the like and ilike operators.",
            DeprecationWarning,
            stacklevel=2,
        )
        value = f"%{value}%"
    return value


_orm_operator_transformer = {
    "neq": lambda value: ("__ne__", value),
    "gt": lambda value: ("__gt__", value),
    "gte": lambda value: ("__ge__", value),
    "in": lambda value: ("in_", value),
    "isnull": lambda value: ("is_", None) if value is True else ("is_not", None),
    "lt": lambda value: ("__lt__", value),
    "lte": lambda value: ("__le__", value),
    "like": lambda value: ("like", _backward_compatible_value_for_like_and_ilike(value)),
    "ilike": lambda value: ("ilike", _backward_compatible_value_for_like_and_ilike(value)),
    # XXX(arthurio): Mysql excludes None values when using `in` or `not in` filters.
    "not": lambda value: ("is_not", value),
    "not_in": lambda value: ("not_in", value),
}
"""Operators à la Django.

Examples:
    my_datetime__gte
    count__lt
    name__isnull
    user_id__in
"""


class Filter(BaseFilterModel):
    """Base filter for orm related filters.

    All children must set:
        ```python
        class Constants(Filter.Constants):
            model = MyModel
        ```

    It can handle regular field names and Django style operators.

    Example:
        ```python
        class MyModel:
            id: PrimaryKey()
            name: StringField(nullable=True)
            count: IntegerField()
            created_at: DatetimeField()

        class MyModelFilter(Filter):
            id: int | None
            id__in: str | None
            count: int | None
            count__lte: int | None
            created_at__gt: datetime | None
            name__isnull: bool | None
    """

    class Direction(str, Enum):  # noqa: UP042 - StrEnum would change str()/format() output (public API)
        asc = "asc"
        desc = "desc"

    def _apply_condition(self, query: Query | Select, field_name: str, operator: str | None, value: Any):
        if operator is None:
            sql_operator = "__eq__"
        else:
            sql_operator, value = _orm_operator_transformer[operator](value)
        model_field = getattr(self.Constants.model, field_name)
        return query.filter(getattr(model_field, sql_operator)(value))

    def _apply_search(self, query: Query | Select, search_fields: list[str], value: Any):
        search_filters = [getattr(self.Constants.model, field).ilike(f"%{value}%") for field in search_fields]
        return query.filter(or_(*search_filters))

    def _apply_nested(self, query: Query | Select, field_name: str, nested: BaseFilterModel, nesting_depth: int):
        return nested.filter(query)

    def _apply_order(self, query: Query | Select, ordering: list[tuple[str, bool]]):
        for field_name, descending in ordering:
            direction = Filter.Direction.desc if descending else Filter.Direction.asc
            order_by_field = getattr(self.Constants.model, field_name)
            query = query.order_by(getattr(order_by_field, direction)())
        return query
