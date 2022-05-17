# -*- coding: utf-8 -*-

from pydantic import validator
from sqlalchemy.orm import Query
from sqlalchemy.sql.selectable import Select

from ...base.filter import BaseFilterModel

_orm_operator_transformer = {
    "gt": lambda value: ("__gt__", value),
    "gte": lambda value: ("__ge__", value),
    "in": lambda value: ("in_", value),
    "isnull": lambda value: ("is_", None) if value is True else ("is_not", None),
    "lt": lambda value: ("__lt__", value),
    "lte": lambda value: ("__le__", value),
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
        class Constants:
            model = orm.MyModel
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

    # Limitation

    You can't set defaults on filter fields in the class definition or they always will be ignored.
    Instead, you should set a value on the instance of the filter class.
    """

    class Constants:
        model = None

    @validator("*", pre=True)
    def split_str(cls, value, field):
        if (field.name.endswith("__in") or field.name.endswith("__not_in")) and isinstance(value, str):
            return [field.type_(v) for v in value.split(",")]
        return value

    def filter(self, query: Query | Select):
        for field_name, value in self.dict(exclude_defaults=True, exclude_unset=True).items():
            field = getattr(self, field_name)
            if isinstance(field, Filter):
                query = field.filter(query)
            else:
                if "__" in field_name:
                    field_name, operator = field_name.split("__")
                    operator, value = _orm_operator_transformer[operator](value)
                else:
                    operator = "__eq__"

                model_field = getattr(self.Constants.model, field_name)
                query = query.filter(getattr(model_field, operator)(value))

        return query
