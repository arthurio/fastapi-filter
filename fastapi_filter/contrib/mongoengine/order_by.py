from mongoengine import QuerySet

from ...base.order_by import BaseOrderBy


class OrderBy(BaseOrderBy):
    """Specialized version of OrderBy for mongoengine."""

    class Constants:
        collection = None

    @classmethod
    def get_constants_field(cls):
        return "collection"

    def sort(self, query: QuerySet):
        if not self.order_by:
            return query
        return query.order_by(*self.order_by.split(","))
