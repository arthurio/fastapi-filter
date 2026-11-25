# -*- coding: utf-8 -*-
from elasticsearch_dsl import Q, Search
from elasticsearch_dsl.query import Query
from pydantic import ValidationInfo, field_validator

from ...base.filter import BaseFilterModel


_operator_transformer = {
    "neq": lambda value, field_name: ~Q("term", **{field_name: value}),
    "gt": lambda value, field_name: Q("range", **{field_name: {"gt": value}}),
    "gte": lambda value, field_name: Q("range", **{field_name: {"gte": value}}),
    "lt": lambda value, field_name: Q("range", **{field_name: {"lt": value}}),
    "lte": lambda value, field_name: Q("range", **{field_name: {"lte": value}}),
    "in": lambda value, field_name: Q("terms", **{field_name: value}),
    "isnull": lambda value, field_name: ~Q("exists", field=field_name)
    if value is True
    else Q("exists", field=field_name),
    "not": lambda value, field_name: ~Q("term", **{field_name: value}),
    "not_in": lambda value, field_name: ~Q("terms", **{field_name: value}),
    "nin": lambda value, field_name: ~Q("terms", **{field_name: value}),
}


class Filter(BaseFilterModel):
    """Base filter for elasticsearch_dsl related filters.

    Example:
        ```python

        class MyModel(Document):
            street = Keyword()
            city = Keyword()
            country = Keyword()
            number = Integer()

        class MyModelFilter(Filter):
            street: Optional[str] = None
            number: Optional[int] = None
            number__gt: Optional[int] = None
            number__gte: Optional[int] = None
            number__lt: Optional[int] = None
            number__lte: Optional[int] = None
            street__isnull: Optional[bool] = None
            country: Optional[str] = None
            country_not: Optional[str] = None
            city: Optional[str] = None
            city__in: Optional[List[str]] = None
            city__not_in: Optional[List[str]] = ["city"]
            custom_order_by: Optional[List[str]] = None
            custom_search: Optional[str] = None
            order_by: List[str] = ["-street"]
        ```
    """

    def sort(self, query: Search) -> Search:
        if not self.ordering_values:
            return query
        return query.sort(*self.ordering_values)

    @field_validator("*", mode="before")
    def split_str(cls, value, field: ValidationInfo):
        if (
            field.field_name is not None
            and (
                field.field_name == cls.Constants.ordering_field_name
                or field.field_name.endswith("__in")
                or field.field_name.endswith("__nin")
                or field.field_name.endswith("__not_in")
            )
            and isinstance(value, str)
        ):
            if not value:
                # Empty string should return [] not ['']
                return []
            return list(value.split(","))
        return value

    def make_query(self, field_name: str, value) -> Query:
        if "__" in field_name:
            field_name, operator = field_name.split("__")
            query = _operator_transformer[operator](value, field_name)
        elif field_name == self.Constants.search_field_name and hasattr(self.Constants, "search_model_fields"):
            query = Q(
                "multi_match",
                type="bool_prefix",
                fields=[
                    field_gram
                    for field in self.Constants.search_model_fields
                    for field_gram in [f"{field}", f"{field}._2gram", f"{field}._3gram"]
                ],
                query=value,
            )
        else:
            query = Q("term", **{field_name: value})
        return query

    def filter(self, search: Search) -> Search:
        queries = Q()
        for field_name, value in self.filtering_fields:
            field_value = getattr(self, field_name)
            if isinstance(field_value, Filter):
                nested_queries = Q()
                for inner_field, inner_value in field_value.filtering_fields:
                    nested_queries &= self.make_query(f"{field_name}.{inner_field}", inner_value)
                search.query("nested", path=field_name, query=nested_queries)
            else:
                queries &= self.make_query(field_name, value)

        return search.query(queries)
