from collections import defaultdict
from collections.abc import Iterable
from copy import deepcopy
from types import UnionType
from typing import Any, ClassVar, Union, get_args, get_origin

from fastapi import Depends
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, ValidationError, ValidationInfo, create_model, field_validator
from pydantic.fields import FieldInfo

UNION_TYPES: list = [Union, UnionType]


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
        """Per-filter configuration.

        Subclasses only need to override what they use, e.g. `class Constants(Filter.Constants): model = MyModel`.
        """

        model: type[Any]
        ordering_field_name: ClassVar[str] = "order_by"
        search_model_fields: ClassVar[list[str]] = []
        """Model fields searched by `search_field_name`. An empty list disables searching."""
        search_field_name: ClassVar[str] = "search"
        prefix: ClassVar[str] = ""
        original_filter: ClassVar[type["BaseFilterModel"] | None] = None

    # ------------------------------------------------------------------
    # Template methods: backends should only override the `_apply_*` /
    # `_finalize_*` / `_split_field_name` hooks below.
    # ------------------------------------------------------------------

    def filter(self, query: Any) -> Any:
        """Apply the filter to `query` by walking the fields and calling the backend hooks."""
        return self._finalize_filter(self._filter_fields(query))

    def _filter_fields(self, query: Any, nesting_depth: int = 1) -> Any:
        """Apply every filtering field of this filter (recursing into nested filters) to `query`."""
        for field_name, value in self.filtering_fields:
            field_value = getattr(self, field_name)
            if isinstance(field_value, BaseFilterModel):
                if not field_value.model_dump(exclude_none=True, exclude_unset=True):
                    continue
                query = self._apply_nested(query, field_name, field_value, nesting_depth)
                continue

            name, operator = self._split_field_name(field_name)
            search_fields = self.Constants.search_model_fields
            if name == self.Constants.search_field_name and search_fields:
                query = self._apply_search(query, search_fields, value)
            else:
                query = self._apply_condition(query, name, operator, value)
        return query

    def _split_field_name(self, field_name: str) -> tuple[str, str | None]:
        """Split `field__operator` into `(field, operator)`; `operator` is None when there is none."""
        if "__" in field_name:
            name, operator = field_name.split("__")
            return name, operator
        return field_name, None

    def _apply_condition(self, query: Any, field_name: str, operator: str | None, value: Any) -> Any:
        """Hook: apply `field_name <operator> value` (operator None means equality) to `query`."""
        raise NotImplementedError

    def _apply_search(self, query: Any, search_fields: list[str], value: Any) -> Any:
        """Hook: apply a search for `value` over `search_fields` to `query`."""
        raise NotImplementedError

    def _apply_nested(self, query: Any, field_name: str, nested: "BaseFilterModel", nesting_depth: int) -> Any:
        """Hook: apply the non-empty `nested` filter found on `field_name`. Defaults to flattening it into `query`."""
        return nested._filter_fields(query, nesting_depth + 1)  # noqa: SLF001

    def _finalize_filter(self, query: Any) -> Any:
        """Hook: last step of `filter()`."""
        return query

    def sort(self, query: Any) -> Any:
        """Apply the ordering to `query`, parsing the `-`/`+` direction prefixes."""
        if not self.ordering_values:
            return query

        ordering: list[tuple[str, bool]] = []
        for field_name in self.ordering_values:
            descending = field_name.startswith("-")
            ordering.append((field_name.replace("-", "").replace("+", ""), descending))
        return self._apply_order(query, ordering)

    def _apply_order(self, query: Any, ordering: list[tuple[str, bool]]) -> Any:
        """Hook: order `query` by `(field_name, descending)` pairs, in order of priority."""
        raise NotImplementedError

    @staticmethod
    def _prefixed_ordering(ordering: list[tuple[str, bool]]) -> list[str]:
        """Serialise `(field_name, descending)` pairs back to `-name` / `+name` strings."""
        return [f"{'-' if descending else '+'}{name}" for name, descending in ordering]

    @property
    def filtering_fields(self):
        fields = self.model_dump(exclude_none=True, exclude_unset=True)
        fields.pop(self.Constants.ordering_field_name, None)
        return fields.items()

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

    # NOTE: Pydantic v2 executes mode="before" validators in REVERSE definition order.
    # So validate_order_by (defined first) runs LAST, after strip and split.

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

    @field_validator("*", mode="before")
    @classmethod
    def split_str(cls, value, field: ValidationInfo):
        if (
            field.field_name is not None
            and (
                field.field_name == cls.Constants.ordering_field_name
                or field.field_name.endswith("__in")
                or field.field_name.endswith("__not_in")
                or field.field_name.endswith("__nin")
            )
            and isinstance(value, str)
        ):
            if not value:
                return []
            return list(value.split(","))
        return value


def with_prefix(prefix: str, Filter: type[BaseFilterModel]) -> type[BaseFilterModel]:
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
    # Class bodies can't read enclosing-function names they also assign, hence the aliases.
    prefix_value = prefix
    original = Filter

    class NestedFilter(Filter):  # type: ignore[misc, valid-type]
        model_config = ConfigDict(extra="forbid", alias_generator=lambda string: f"{prefix}__{string}")

        class Constants(Filter.Constants):  # type: ignore[name-defined]
            prefix = prefix_value
            original_filter = original

    return NestedFilter


def _list_to_str_fields(Filter: type[BaseFilterModel]):
    ret: dict[str, tuple[object | type, FieldInfo | None]] = {}
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
            ret[name] = (str if f.is_required() else str | None, field_info)
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
                if original_filter := Filter.Constants.original_filter:
                    prefix = f"{Filter.Constants.prefix}__"
                    stripped = {k.removeprefix(prefix): v for k, v in data.items()}
                    return original_filter(**stripped)
                return Filter(**data)
            except ValidationError as e:
                raise RequestValidationError(e.errors()) from e

    return Depends(FilterWrapper)
