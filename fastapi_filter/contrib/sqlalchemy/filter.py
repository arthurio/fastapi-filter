# -*- coding: utf-8 -*-
from enum import Enum
from typing import List, Tuple, Union, Any
from warnings import warn

from pydantic import BaseModel, ValidationInfo, field_validator
from sqlalchemy import or_
from sqlalchemy.orm import Query, class_mapper, RelationshipProperty
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
            id: Optional[int]
            id__in: Optional[str]
            count: Optional[int]
            count__lte: Optional[int]
            created_at__gt: Optional[datetime]
            name__isnull: Optional[bool]
    """

    class Direction(str, Enum):
        asc = "asc"
        desc = "desc"

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

    def filter(self, query: Union[Query, Select]):
        relationships = _get_relationships(self.Constants.model)
        query = self._join_relationships(query, relationships)
        query = self._apply_filters(query)
        return query

    def _join_relationships(self, query: Union[Query, Select], relationships: List[Tuple[Any, RelationshipProperty]]):
        """Joins the specified relationships in the query.

        Args:
            query (Union[Query, Select]): The SQLAlchemy query object.
            relationships (List[Tuple[Any, RelationshipProperty]]): The list of relationships to join.

        Returns:
            Union[Query, Select]: The modified query object with the joined relationships.
        """
        for rel_class, rel in relationships:
            related_filter = next(
                (value for key, value in self.filtering_fields if key == rel.key),
                None,
            )
            if related_filter is not None and _any_field_not_none(related_filter):
                if rel.secondary is not None:
                    query = query.outerjoin(rel.secondary, rel.primaryjoin)
                    query = query.outerjoin(rel_class, rel.secondaryjoin)
                else:
                    query = query.outerjoin(rel_class, rel.primaryjoin)
        return query

    def _apply_filters(self, query: Union[Query, Select]):
        """Apply the filtering fields to the given query.

        Args:
            query (Union[Query, Select]): The query to apply the filters to.

        Returns:
            Union[Query, Select]: The modified query with the filters applied.
        """
        for field_name, value in self.filtering_fields:
            field_value = getattr(self, field_name)
            if isinstance(field_value, Filter):
                query = field_value.filter(query)
            else:
                if "__" in field_name:
                    field_name, operator = field_name.split("__")
                    operator, value = _orm_operator_transformer[operator](value)
                else:
                    operator = "__eq__"

                if field_name == self.Constants.search_field_name and hasattr(self.Constants, "search_model_fields"):
                    search_filters = [
                        getattr(self.Constants.model, field).ilike(f"%{value}%")
                        for field in self.Constants.search_model_fields
                    ]
                    query = query.filter(or_(*search_filters))
                else:
                    model_field = getattr(self.Constants.model, field_name)
                    query = query.filter(getattr(model_field, operator)(value))

        return query

    def sort(self, query: Union[Query, Select]):
        if not self.ordering_values:
            return query

        for field_name in self.ordering_values:
            direction = Filter.Direction.asc
            if field_name.startswith("-"):
                direction = Filter.Direction.desc
            field_name = field_name.replace("-", "").replace("+", "")

            order_by_field = getattr(self.Constants.model, field_name)

            query = query.order_by(getattr(order_by_field, direction)())

        return query


def _get_relationships(model: Any) -> List[Tuple[Any, RelationshipProperty]]:
    """Get the related classes and relationship attributes of a SQLAlchemy model.

    Args:
        model (Any): The SQLAlchemy model.

    Returns:
        List[Tuple[Any, RelationshipProperty]]: A list of tuples, where each tuple contains a SQLAlchemy ORM class related to the model and the corresponding relationship attribute.
    """
    mapper = class_mapper(model)
    relationships = [(rel.mapper.class_, rel) for rel in mapper.relationships]
    return relationships


def _any_field_not_none(model: dict) -> bool:
    """Check if any field in a Pydantic model or any of its nested models is not None.

    Args:
        model (BaseModel): The dict representation of a model.

    Returns:
        bool: True if any field is not None, False otherwise.
    """
    for _field, value in model.items():
        if value is not None:
            if isinstance(value, dict):
                # If the value is a nested model, check if any field in the nested model is not None
                if _any_field_not_none(value):
                    return True
            else:
                return True
    return False
