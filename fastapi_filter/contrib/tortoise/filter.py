from functools import reduce
from typing import Union
from warnings import warn
from operator import or_

from pydantic import ValidationInfo, field_validator
from tortoise.queryset import QuerySet, Q


from ...base.filter import BaseFilterModel




_orm_operator_transformer = {
    "neq": lambda value: ("__not", value),
    "gt": lambda value: ("__gt", value),
    "gte": lambda value: ("__gte", value),
    "in": lambda value: ("__in", value),
    "isnull": lambda value: ("__isnull", True),
    "lt": lambda value: ("__lt", value),
    "lte": lambda value: ("__lte", value),
    "like": lambda value: ("__contains", value),
    "ilike": lambda value: ("__icontains", value),
    "not": lambda value: ("__not", value),
    "not_in": lambda value: ("__not_in", value),
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
            id: Optional[int]
            id__in: Optional[str]
            count: Optional[int]
            count__lte: Optional[int]
            created_at__gt: Optional[datetime]
            name__isnull: Optional[bool]
    """

    @field_validator("*", mode="before")
    def split_str(cls, value, field: ValidationInfo):
        if (
            field.field_name is not None
            and (
                field.field_name == cls.Constants.ordering_field_name
                or field.field_name.endswith("__in")
                or field.field_name.endswith("__not_in")
            )
            and isinstance(value, str)
        ):
            if not value:
                # Empty string should return [] not ['']
                return []
            return list(value.split(","))
        return value

    def filter(self, query: QuerySet):
        for field_name, value in self.filtering_fields:
            field_value = getattr(self, field_name)
            if isinstance(field_value, Filter):
                query = field_value.filter(query)
            else:
                if "__" in field_name:
                    field_name, operator = field_name.split("__")
                    operator, value = _orm_operator_transformer[operator](value)
                else:
                    operator = ""

                if field_name == self.Constants.search_field_name and hasattr(self.Constants, "search_model_fields"):
                    search_filters = [
                        {f'{field}__icontains': value}
                        for field in self.Constants.search_model_fields
                    ]
                    query = query.filter(reduce(or_, [Q(**filt) for filt in search_filters]))
                else:
                    query = query.filter(**{f'{field_name}{operator}': value})

        return query

    def sort(self, query: QuerySet):
        if not self.ordering_values:
            return query

        return query.order_by(*self.ordering_values)
