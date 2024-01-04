from mongoengine import QuerySet
from mongoengine.queryset.visitor import Q
from pydantic import ValidationInfo, field_validator

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
            id: Optional[int]
            id__in: Optional[str]
            count: Optional[int]
            count__lte: Optional[int]
            created_at__gt: Optional[datetime]
            name__ne: Optional[str]
            name__nin: Optional[list[str]]
            name__isnull: Optional[bool]
        ```
    """

    def sort(self, query: QuerySet) -> QuerySet:
        if not self.ordering_values:
            return query
        return query.order_by(*self.ordering_values)

    @field_validator("*", mode="before")
    def split_str(cls, value, field: ValidationInfo):
        if (
            field.field_name is not None
            and (
                field.field_name == cls.Constants.ordering_field_name
                or field.field_name.endswith("__in")
                or field.field_name.endswith("__nin")
            )
            and isinstance(value, str)
        ):
            if not value:
                # Empty string should return [] not ['']
                return []
            return list(value.split(","))
        return value

    def filter(self, query: QuerySet) -> QuerySet:
        for field_name, value in self.filtering_fields:
            field_value = getattr(self, field_name)
            if isinstance(field_value, Filter):
                if not field_value.model_dump(exclude_none=True, exclude_unset=True):
                    continue

                query = query.filter(**{f"{field_name}__in": field_value.filter(field_value.Constants.model.objects())})
            else:
                if field_name.endswith("__isnull"):
                    field_name = field_name.replace("__isnull", "")
                    if value is False:
                        field_name = f"{field_name}__ne"
                    value = None

                if field_name == self.Constants.search_field_name and hasattr(self.Constants, "search_model_fields"):
                    search_filter = Q()
                    for search_field in self.Constants.search_model_fields:
                        search_filter = search_filter | Q(**{f"{search_field}__icontains": value})

                    query = query.filter(search_filter)
                else:
                    query = query.filter(**{field_name: value})

        return query
