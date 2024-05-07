import sys
from collections import defaultdict
from collections.abc import Iterable
from copy import deepcopy
from typing import Any, Optional, Union, get_args, get_origin

from fastapi import Depends
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, ValidationError, ValidationInfo, create_model, field_validator
from pydantic.fields import FieldInfo

UNION_TYPES: list = [Union]

if sys.version_info >= (3, 10):
    from types import UnionType

    UNION_TYPES.append(UnionType)


class BaseFilterModel(BaseModel, extra="forbid"):
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
        model: Any
        ordering_field_name: str = "order_by"
        search_model_fields: list[str]
        search_field_name: str = "search"
        prefix: str
        original_filter: type["BaseFilterModel"]

    def filter(self, query):  # pragma: no cover
        ...

    @property
    def filtering_fields(self):
        fields = self.model_dump(exclude_none=True, exclude_unset=True)
        fields.pop(self.Constants.ordering_field_name, None)
        return fields.items()

    def sort(self, query):  # pragma: no cover
        ...

    @property
    def ordering_values(self):
        """Check that the ordering field is present on the class definition."""
        try:
            return getattr(self, self.Constants.ordering_field_name)
        except AttributeError as e:
            raise AttributeError(
                f"Ordering field {self.Constants.ordering_field_name} is not defined. "
                "Make sure to add it to your filter class."
            ) from e

    @field_validator("*", mode="before", check_fields=False)
    def strip_order_by_values(cls, value, field: ValidationInfo):
        if field.field_name != cls.Constants.ordering_field_name:
            return value

        if not value:
            return None

        stripped_values = []
        for field_name in value:
            stripped_value = field_name.strip()
            if stripped_value:
                stripped_values.append(stripped_value)

        return stripped_values

    @field_validator("*", mode="before", check_fields=False)
    def validate_order_by(cls, value, field: ValidationInfo):
        if field.field_name != cls.Constants.ordering_field_name:
            return value

        if not value:
            return None

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


def with_prefix(prefix: str, Filter: type[BaseFilterModel]) -> type[BaseFilterModel]:
    """Allow re-using existing filter under a prefix.

    Example:
        ```python
        from pydantic import BaseModel

        from fastapi_filter.filter import FilterDepends

        class NumberFilter(BaseModel):
            count: Optional[int]

        class MainFilter(BaseModel):
            name: str
            number_filter: Optional[Filter] = FilterDepends(with_prefix("number_filter", Filter))
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
            count: Optional[int] = Query(default=10, alias=counter)

        class MainFilter(BaseModel):
            name: str
            number_filter: Optional[Filter] = FilterDepends(with_prefix("number_filter", Filter))
        ```

    As a result, you'll get the following filters:
        * name
        * counter (*NOT* number_filter__counter)
    """

    class NestedFilter(Filter):  # type: ignore[misc, valid-type]
        model_config = ConfigDict(extra="forbid", alias_generator=lambda string: f"{prefix}__{string}")

        class Constants(Filter.Constants):  # type: ignore[name-defined]
            ...

    NestedFilter.Constants.prefix = prefix
    NestedFilter.Constants.original_filter = Filter

    return NestedFilter


def _list_to_str_fields(Filter: type[BaseFilterModel]):
    ret: dict[str, tuple[Union[object, type], Optional[FieldInfo]]] = {}
    for name, f in Filter.model_fields.items():
        field_info = deepcopy(f)
        annotation = f.annotation

        if get_origin(annotation) in UNION_TYPES:
            annotation_args: list = list(get_args(f.annotation))
            if type(None) in annotation_args:
                annotation_args.remove(type(None))
            if len(annotation_args) == 1:
                annotation = annotation_args[0]
            # NOTE: This doesn't support union types which contain list and other types at the
            # same time like `list[str] | str` or `list[str] | str | None`. The list type inside
            # union will not be converted to string which means that the filter will not work in
            # such cases.
            # We cannot raise exception here because we still want to support union types in
            # filter for example `int | float | None` is valid type and should not be transformed.

        if annotation is list or get_origin(annotation) is list:
            if isinstance(field_info.default, Iterable):
                field_info.default = ",".join(field_info.default)
            ret[name] = (str if f.is_required() else Optional[str], field_info)
        else:
            ret[name] = (f.annotation, field_info)

    return ret


def FilterDepends(Filter: type[BaseFilterModel], *, by_alias: bool = False, use_cache: bool = True) -> Any:
    """Use a hack to support lists in filters.

    FastAPI doesn't support it yet: https://github.com/tiangolo/fastapi/issues/50

    What we do is loop through the fields of a filter and change any `list` field to a `str` one so that it won't be
    excluded from the possible query parameters.

    When we apply the filter, we build the original filter to properly validate the data (i.e. can the string be parsed
    and formatted as a list of <type>?)
    """
    fields = _list_to_str_fields(Filter)
    GeneratedFilter: type[BaseFilterModel] = create_model(Filter.__class__.__name__, **fields)

    class FilterWrapper(GeneratedFilter):  # type: ignore[misc,valid-type]
        def __new__(cls, *args, **kwargs):
            try:
                instance = GeneratedFilter(*args, **kwargs)
                data = instance.model_dump(exclude_unset=True, exclude_defaults=True, by_alias=by_alias)
                if original_filter := getattr(Filter.Constants, "original_filter", None):
                    prefix = f"{Filter.Constants.prefix}__"
                    stripped = {k.removeprefix(prefix): v for k, v in data.items()}
                    return original_filter(**stripped)
                return Filter(**data)
            except ValidationError as e:
                raise RequestValidationError(e.errors()) from e

    return Depends(FilterWrapper)
