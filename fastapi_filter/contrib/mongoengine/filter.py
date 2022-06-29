from mongoengine import Document, QuerySet
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

    # Limitation

    You can't set defaults on filter fields in the class definition or they always will be ignored.
    Instead, you should set a value on the instance of the filter class.
    """

    class Constants:
        collection: Document
        prefix: str

    @validator("*", pre=True)
    def split_str(cls, value, field):
        if (field.name.endswith("__in") or field.name.endswith("__nin")) and isinstance(value, str):
            return [field.type_(v) for v in value.split(",")]
        return value

    def filter(self, query: QuerySet):
        for field_name, value in self.dict(exclude_none=True, exclude_unset=True).items():
            field_value = getattr(self, field_name)
            if isinstance(field_value, Filter):
                if not field_value.dict(exclude_none=True, exclude_unset=True):
                    continue
                query = query.filter(
                    **{
                        f"{field_value.Constants.prefix}__in": field_value.filter(
                            field_value.Constants.collection.objects()
                        )
                    }
                )
            else:
                if field_name.endswith("__isnull"):
                    field_name = field_name.replace("__isnull", "")
                    if value is False:
                        field_name = f"{field_name}__ne"
                    value = None

                query = query.filter(**{field_name: value})

        return query
