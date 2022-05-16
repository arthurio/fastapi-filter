from enum import Enum

from sqlalchemy.orm import Query

from ...base.order_by import BaseOrderBy


class OrderBy(BaseOrderBy):
    """Specialized version of OrderBy for sqlalchemy."""

    class Direction(str, Enum):
        asc = "asc"
        desc = "desc"

    class Constants:
        model = None

    @classmethod
    def get_constants_field(cls):
        return "model"

    def sort(self, query: Query):
        if not self.order_by:
            return query

        for field_name in self.order_by.split(","):
            direction = OrderBy.Direction.asc
            if field_name.startswith("-"):
                direction = OrderBy.Direction.desc
            field_name = field_name.replace("-", "").replace("+", "")

            order_by_field = getattr(self.Constants.model, field_name)

            query = query.order_by(getattr(order_by_field, direction)())

        return query
