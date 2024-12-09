from collections.abc import Callable, Mapping
from typing import Any, Optional, Union

from beanie.odm.interfaces.find import FindType
from beanie.odm.queries.find import FindMany
from pydantic import ValidationInfo, field_validator

from fastapi_filter.base.filter import BaseFilterModel

_odm_operator_transformer: dict[str, Callable[[Optional[str]], Optional[dict[str, Any]]]] = {
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

    def sort(self, query: FindMany[FindType]) -> FindMany[FindType]:
        if not self.ordering_values:
            return query
        return query.sort(*self.ordering_values)

    @field_validator("*", mode="before")
    @classmethod
    def split_str(
        cls: type["BaseFilterModel"], value: Optional[str], field: ValidationInfo
    ) -> Optional[Union[list[str], str]]:
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

    def _get_filter_conditions(self, nesting_depth: int = 1) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
        filter_conditions: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
        for field_name, value in self.filtering_fields:
            field_value = getattr(self, field_name)
            if isinstance(field_value, Filter):
                if not field_value.model_dump(exclude_none=True, exclude_unset=True):
                    continue

                filter_conditions.append(
                    (
                        {field_name: _odm_operator_transformer["neq"](None)},
                        {"fetch_links": True, "nesting_depth": nesting_depth},
                    )
                )
                for part, part_options in field_value._get_filter_conditions(nesting_depth=nesting_depth + 1):  # noqa: SLF001
                    for sub_field_name, sub_value in part.items():
                        filter_conditions.append(
                            (
                                {f"{field_name}.{sub_field_name}": sub_value},
                                {"fetch_links": True, "nesting_depth": nesting_depth, **part_options},
                            )
                        )

            elif "__" in field_name:
                stripped_field_name, operator = field_name.split("__")
                search_criteria = _odm_operator_transformer[operator](value)
                filter_conditions.append(({stripped_field_name: search_criteria}, {}))
            elif field_name == self.Constants.search_field_name and hasattr(self.Constants, "search_model_fields"):
                search_conditions = [
                    {search_field: _odm_operator_transformer["ilike"](value)}
                    for search_field in self.Constants.search_model_fields
                ]
                filter_conditions.append(({"$or": search_conditions}, {}))
            else:
                filter_conditions.append(({field_name: value}, {}))

        return filter_conditions

    def filter(self, query: FindMany[FindType]) -> FindMany[FindType]:
        data = self._get_filter_conditions()
        for filter_condition, filter_kwargs in data:
            query = query.find(filter_condition, **filter_kwargs)
        return query.find(fetch_links=True)
