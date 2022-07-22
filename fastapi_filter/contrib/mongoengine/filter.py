from mongoengine import QuerySet
from pydantic import validator

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

    def sort(self, query: QuerySet):
        if not self.ordering_values:
            return query
        return query.order_by(*self.ordering_values)

    @validator("*", pre=True)
    def split_str(cls, value, field):
        if (
            field.name == cls.Constants.ordering_field_name
            or field.name.endswith("__in")
            or field.name.endswith("__nin")
        ) and isinstance(value, str):
            return [field.type_(v) for v in value.split(",")]
        return value

    def filter(self, query: QuerySet):
        for field_name, value in self.filtering_fields:
            field_value = getattr(self, field_name)
            if isinstance(field_value, Filter):
                if not field_value.dict(exclude_none=True, exclude_unset=True):
                    continue
                query = query.filter(
                    **{f"{field_value.Constants.prefix}__in": field_value.filter(field_value.Constants.model.objects())}
                )
            else:
                if field_name.endswith("__isnull"):
                    field_name = field_name.replace("__isnull", "")
                    if value is False:
                        field_name = f"{field_name}__ne"
                    value = None

                query = query.filter(**{field_name: value})

        return query
