from copy import deepcopy
from typing import Any, Type

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Extra, ValidationError, create_model, fields, validator
from pydantic.fields import FieldInfo


class BaseFilterModel(BaseModel, extra=Extra.forbid):
    class Constants:
        ...

    def filter(self, query):
        ...

    @validator("*", pre=True)
    def split_str(cls, value, field):
        ...


def nested_filter(prefix: str, Filter: Type[BaseFilterModel]):
    """Allow re-using existing filter under a prefix.

    Example:
        ```python
        from pydantic import BaseModel
        from fastapi_filter.filter import FilterDepends

        class NumberFilter(BaseModel):
            count: int | None

        class MainFilter(BaseModel):
            name: str
            number_filter: Filter | None = FilterDepends(nested_filter("number_filter", Filter))
        ```

    As a result, you'll get the following filters:
        * name
        * number_filter__count

    # Limitation

    The alias generator is the last to be picked in order of prevalence. So if one the fields has a `Query` as default
    and declares an alias already, this will be picked first and you won't get the prefix.

    Example:
        ```python
         from pydantic import BaseModel

        class NumberFilter(BaseModel):
            count: Optional[int] = Query(default=10, alias=counter)

        class MainFilter(BaseModel):
            name: str
            number_filter: Optional[Filter] = FilterDepends(nested_filter("number_filter", Filter))
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

    return NestedFilter


def _list_to_str_fields(Filter: Type[BaseFilterModel]):
    ret: dict[str, tuple[object | Type, FieldInfo | None]] = {}
    for f in Filter.__fields__.values():
        field_info = deepcopy(f.field_info)
        if f.shape == fields.SHAPE_LIST:
            ret[f.name] = (str | None, field_info)
        else:
            field_type = Filter.__annotations__.get(f.name, f.outer_type_)
            ret[f.name] = (field_type | None, field_info)

    return ret


def FilterDepends(Filter: Type[BaseFilterModel], *, use_cache: bool = True) -> Any:
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
                original_filter = Filter(**self.dict())
            except ValidationError as e:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
            return original_filter.filter(*args, **kwargs)

    return Depends(FilterWrapper)
