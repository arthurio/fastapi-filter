from typing import Any

from mongoengine import QuerySet
from mongoengine.queryset.visitor import Q

from ...base.filter import BaseFilterModel


class Filter(BaseFilterModel):
    """Base filter for mongoengine related filters.

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

    def _split_field_name(self, field_name: str) -> tuple[str, str | None]:
        # Only `isnull` is rewritten; every other `field__operator` is understood natively by mongoengine.
        if field_name.endswith("__isnull"):
            return field_name.removesuffix("__isnull"), "isnull"
        return field_name, None

    def _apply_condition(self, query: QuerySet, field_name: str, operator: str | None, value: Any) -> QuerySet:
        if operator == "isnull":
            return query.filter(**{f"{field_name}__ne" if value is False else field_name: None})
        return query.filter(**{field_name: value})

    def _apply_search(self, query: QuerySet, search_fields: list[str], value: Any) -> QuerySet:
        search_filter = Q()
        for search_field in search_fields:
            search_filter = search_filter | Q(**{f"{search_field}__icontains": value})
        return query.filter(search_filter)

    def _apply_nested(self, query: QuerySet, field_name: str, nested: BaseFilterModel, nesting_depth: int) -> QuerySet:
        return query.filter(**{f"{field_name}__in": nested.filter(nested.Constants.model.objects())})

    def _apply_order(self, query: QuerySet, ordering: list[tuple[str, bool]]) -> QuerySet:
        return query.order_by(*[f"{'-' if descending else '+'}{name}" for name, descending in ordering])
