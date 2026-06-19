"""fastapi-filter: Declarative query-parameter filtering for FastAPI.

For simple (non-nested) filter classes, prefer the native FastAPI pattern::

    from typing import Annotated
    from fastapi import Query
    from fastapi_filter.contrib.sqlalchemy import Filter

    @app.get("/users")
    async def get_users(user_filter: Annotated[UserFilter, Query()]):
        ...

For nested filters (using ``with_prefix``), use ``FilterDepends``::

    from fastapi_filter import FilterDepends, with_prefix
"""

from .base.filter import FilterDepends, with_prefix

__all__ = (
    "FilterDepends",
    "with_prefix",
)
