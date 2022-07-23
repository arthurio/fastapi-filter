from datetime import datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from pydantic import BaseModel, validator


@pytest_asyncio.fixture(scope="function")
async def test_client(app):
    async with AsyncClient(app=app, base_url="http://test") as async_test_client:
        yield async_test_client


@pytest.fixture(scope="package")
def UserFilterOrderByWithDefault(User, UserFilter):
    class UserFilterOrderByWithDefault(UserFilter):
        order_by: list[str] = ["age"]

    return UserFilterOrderByWithDefault


@pytest.fixture(scope="package")
def UserFilterOrderBy(User, UserFilter):
    class UserFilterOrderBy(UserFilter):
        order_by: list[str] | None

    return UserFilterOrderBy


@pytest.fixture(scope="package")
def UserFilterNoOrderBy(User, UserFilter):
    return UserFilter


@pytest.fixture(scope="package")
def UserFilterCustomOrderBy(UserFilter):
    class UserFilterCustomOrderBy(UserFilter):
        class Constants(UserFilter.Constants):
            ordering_field_name = "custom_order_by"

        custom_order_by: list[str] | None

    return UserFilterCustomOrderBy


@pytest.fixture(scope="package")
def UserFilterRestrictedOrderBy(UserFilter):
    class UserFilterRestrictedOrderBy(UserFilter):
        order_by: list[str] | None

        @validator("order_by", allow_reuse=True)
        def restrict_sortable_fields(cls, value):
            if value is None:
                return None

            allowed_field_names = ["age", "created_at"]
            for field_name in value:
                field_name = field_name.replace("-", "").replace("+", "")

                if field_name not in allowed_field_names:
                    raise ValueError(f"You may only sort by: {', '.join(allowed_field_names)}")

            return value

    return UserFilterRestrictedOrderBy


@pytest.fixture(scope="session")
def AddressOut():
    class AddressOut(BaseModel):
        id: int
        street: str | None
        city: str
        country: str

        class Config:
            orm_mode = True

    return AddressOut


@pytest.fixture(scope="session")
def UserOut(AddressOut):
    class UserOut(BaseModel):
        id: int
        created_at: datetime
        updated_at: datetime
        name: str | None
        age: int
        address: AddressOut | None

        class Config:
            orm_mode = True

    return UserOut
