from datetime import datetime

import pytest
from httpx import AsyncClient
from pydantic import BaseModel


@pytest.fixture(scope="function")
async def test_client(app):
    async with AsyncClient(app=app, base_url="http://test") as async_test_client:
        yield async_test_client


@pytest.fixture(scope="package")
def UserFilterOrderByWithDefault(User, UserFilter):
    class UserFilterOrderByWithDefault(UserFilter):
        class Constants(UserFilter.Constants):
            model = User

        order_by: list[str] = ["age"]

    yield UserFilterOrderByWithDefault


@pytest.fixture(scope="package")
def UserFilterOrderBy(User, UserFilter):
    class UserFilterOrderBy(UserFilter):
        class Constants(UserFilter.Constants):
            model = User

        order_by: list[str] | None

    yield UserFilterOrderBy


@pytest.fixture(scope="package")
def UserFilterNoOrderBy(User, UserFilter):
    class UserFilterNoOrderBy(UserFilter):
        class Constants(UserFilter.Constants):
            model = User

    yield UserFilterNoOrderBy


@pytest.fixture(scope="session")
def AddressOut():
    class AddressOut(BaseModel):
        id: int
        street: str | None
        city: str
        country: str

        class Config:
            orm_mode = True

    yield AddressOut


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

    yield UserOut
