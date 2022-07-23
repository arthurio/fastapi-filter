from collections import defaultdict
from collections.abc import Iterable
from copy import deepcopy
from typing import Any, Type

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Extra, ValidationError, create_model, fields, validator
from pydantic.fields import FieldInfo


class BaseFilterModel(BaseModel, extra=Extra.forbid):
    """Abstract base filter class.

    Provides the interface for filtering and ordering.


    # Ordering

    ## Query string examples:

        >>> "?order_by=-created_at"
        >>> "?order_by=created_at,updated_at"
        >>> "?order_by=+created_at,-name"

    ## Limitation

    Sorting doesn't support related fields, you can only use the attributes of the targeted model/collection.
    For example, you can't use `related_model__attribute`.

    # Filtering

    ## Query string examples:

        >>> "?my_field__gt=12&my_other_field=Tomato"
        >>> "?my_field__in=12,13,15&my_other_field__not_in=Tomato,Pepper"
    """

    class Constants:  # pragma: no cover
        model: Type
        ordering_field_name: str = "order_by"
        prefix: str

    def filter(self, query):  # pragma: no cover
        ...

    @property
    def filtering_fields(self):
        fields = self.dict(exclude_none=True, exclude_unset=True)
        fields.pop(self.Constants.ordering_field_name, None)
        return fields.items()

    def sort(self, query):  # pragma: no cover
        ...

    @property
    def ordering_values(self):
        """Check that the ordering field is present on the class definition."""
        try:
            return getattr(self, self.Constants.ordering_field_name)
        except AttributeError:
            raise AttributeError(
                f"Ordering field {self.Constants.ordering_field_name} is not defined. "
                "Make sure to add it to your filter class."
            )

    @validator("*", pre=True)
    def split_str(cls, value, field):  # pragma: no cover
        ...

    @validator(Constants.ordering_field_name, allow_reuse=True, check_fields=False)
    def validate_order_by(cls, value):
        if not value:
            return value

        field_name_usages = defaultdict(list)
        duplicated_field_names = set()

        for field_name_with_direction in value:
            field_name = field_name_with_direction.replace("-", "").replace("+", "")

            if not hasattr(cls.Constants.model, field_name):
                raise ValueError(f"{field_name} is not a valid ordering field.")

            field_name_usages[field_name].append(field_name_with_direction)
            if len(field_name_usages[field_name]) > 1:
                duplicated_field_names.add(field_name)

        if duplicated_field_names:
            ambiguous_field_names = ", ".join(
                [
                    field_name_with_direction
                    for field_name in sorted(duplicated_field_names)
                    for field_name_with_direction in field_name_usages[field_name]
                ]
            )
            raise ValueError(
                f"Field names can appear at most once for {cls.Constants.ordering_field_name}. "
                f"The following was ambiguous: {ambiguous_field_names}."
            )

        return value


def with_prefix(prefix: str, Filter: Type[BaseFilterModel]):
    """Allow re-using existing filter under a prefix.

    Example:
        ```python
        from pydantic import BaseModel

        from fastapi_filter.filter import FilterDepends

        class NumberFilter(BaseModel):
            count: int | None

        class MainFilter(BaseModel):
            name: str
            number_filter: Filter | None = FilterDepends(with_prefix("number_filter", Filter))
        ```

    As a result, you'll get the following filters:
        * name
        * number_filter__count

    # Limitation

    The alias generator is the last to be picked in order of prevalence. So if one of the fields has a `Query` as
    default and declares an alias already, this will be picked first and you won't get the prefix.

    Example:
        ```python
         from pydantic import BaseModel

        class NumberFilter(BaseModel):
            count: int | None = Query(default=10, alias=counter)

        class MainFilter(BaseModel):
            name: str
            number_filter: Filter | None = FilterDepends(with_prefix("number_filter", Filter))
        ```

    As a result, you'll get the following filters:
        * name
        * counter (*NOT* number_filter__counter)
    """

    class NestedFilter(Filter):  # type: ignore[misc, valid-type]
        class Config:
            extra = Extra.forbid

            @classmethod
            def alias_generator(cls, string: str) -> str:
                return f"{prefix}__{string}"

    NestedFilter.Constants.prefix = prefix

    return NestedFilter


def _list_to_str_fields(Filter: Type[BaseFilterModel]):
    ret: dict[str, tuple[object | Type, FieldInfo | None]] = {}
    for f in Filter.__fields__.values():
        field_info = deepcopy(f.field_info)
        if f.shape == fields.SHAPE_LIST:
            if isinstance(field_info.default, Iterable):
                field_info.default = ",".join(field_info.default)
            ret[f.name] = (str | None, field_info)
        else:
            field_type = Filter.__annotations__.get(f.name, f.outer_type_)
            ret[f.name] = (field_type | None, field_info)

    return ret


def FilterDepends(Filter: Type[BaseFilterModel], *, by_alias: bool = False, use_cache: bool = True) -> Any:
    """This is a hack to support lists in filters.

    Fastapi doesn't support it yet: https://github.com/tiangolo/fastapi/issues/50

    What we do is loop through the fields of a filter and change any `list` field to a `str` one so that it won't be
    excluded from the possible query parameters.

    When we apply the filter, we build the original filter to properly validate the data (i.e. can the string be parsed
    and formatted as a list of <type>?)
    """
    fields = _list_to_str_fields(Filter)
    GeneratedFilter: Type[BaseFilterModel] = create_model(Filter.__class__.__name__, **fields)

    class FilterWrapper(GeneratedFilter):  # type: ignore[misc,valid-type]
        def filter(self, *args, **kwargs):
            try:
                original_filter = Filter(**self.dict(by_alias=by_alias))
            except ValidationError as e:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
            return original_filter.filter(*args, **kwargs)

        def sort(self, *args, **kwargs):
            try:
                original_filter = Filter(**self.dict(by_alias=by_alias))
            except ValidationError as e:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
            return original_filter.sort(*args, **kwargs)

    return Depends(FilterWrapper)
