from mongoengine import QuerySet
from pydantic import validator

from ...base.filter import BaseFilterModel


class Filter(BaseFilterModel):
    """Base filter for mongoengine related filters.

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
            name__ne: Optional[str]
            name__nin: Optional[list[str]]
            name__isnull: Optional[bool]

    # Limitation

    You can't set defaults on filter fields in the class definition or they always will be ignored.
    Instead, you should set a value on the instance of the filter class.
    """

    @validator("*", pre=True)
    def split_str(cls, value, field):
        if (field.name.endswith("__in") or field.name.endswith("__nin")) and isinstance(value, str):
            return [field.type_(v) for v in value.split(",")]
        return value

    def filter(self, query: QuerySet):
        for field_name, value in self.dict(exclude_defaults=True, exclude_unset=True).items():
            if field_name.endswith("__isnull"):
                field_name = field_name.replace("__isnull", "")
                if value is False:
                    field_name = f"{field_name}__ne"
                value = None

            query = query.filter(**{field_name: value})

        return query
