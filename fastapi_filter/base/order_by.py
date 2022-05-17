from pydantic import BaseModel, validator


class BaseOrderBy(BaseModel):
    """Sort queries by one or many fields.

    # Examples:

        >>> "-created_at"
        >>> "created_at,updated_at"
        >>> "+created_at,-name"

    # Limitation

    Sorting doesn't support related fields, you can only use the attributes of the targeted model/collection.
    For example, you can't use `related_model__attribute`.
    """

    order_by: str | None

    class Constants:
        ...

    def sort(self, query):
        ...

    @classmethod
    def get_constants_field(self):
        ...

    @validator("order_by", allow_reuse=True)
    def validate_order_by(cls, value):
        if not value:
            return value

        value = value.replace(" ", "")

        for field_name in value.split(","):
            # Remove direction
            field_name = field_name.replace("-", "").replace("+", "")

            field = getattr(cls.Constants, cls.get_constants_field())

            if not hasattr(field, field_name):
                raise ValueError(f"{field_name} is not a valid ordering field.")

        return value
