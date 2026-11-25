from typing import Annotated

from fastapi import FastAPI, Query
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from fastapi_filter import FilterDepends
from fastapi_filter.contrib.sqlalchemy import Filter


class User:
    is_discharged = None


class UserFilter(Filter):
    is_discharged: bool | SkipJsonSchema[None] = Field(Query(default=None))

    class Constants(Filter.Constants):
        model = User


def test_filter_depends_does_not_emit_unset_openapi_example():
    app = FastAPI()

    @app.get("/users")
    def list_users(filters: Annotated[UserFilter, FilterDepends(UserFilter)]):
        return {}

    parameter = app.openapi()["paths"]["/users"]["get"]["parameters"][0]
    assert "example" not in parameter


def test_filter_depends_preserves_explicit_openapi_example():
    class ExplicitExampleFilter(Filter):
        is_discharged: bool | SkipJsonSchema[None] = Field(Query(default=None, examples=[True]))

        class Constants(Filter.Constants):
            model = User

    app = FastAPI()

    @app.get("/users")
    def list_users(filters: Annotated[ExplicitExampleFilter, FilterDepends(ExplicitExampleFilter)]):
        return {}

    parameter = app.openapi()["paths"]["/users"]["get"]["parameters"][0]
    assert parameter["schema"]["examples"] == [True]
