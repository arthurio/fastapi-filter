from datetime import datetime

import pytest
from mongoengine import Document, connect, fields


@pytest.fixture(scope="session")
def database_url() -> str:
    return "mongodb://127.0.0.1"


@pytest.fixture(scope="session")
def db_connect(database_url):
    connect(host=database_url, uuidRepresentation="standard")


@pytest.fixture(scope="session")
def User(db_connect):
    class User(Document):
        name = fields.StringField(null=True)
        age = fields.IntField()
        created_at = fields.DateTimeField()

    return User


@pytest.fixture(scope="function")
def users(User):
    User(name=None, age=21, created_at=datetime(2021, 12, 1)).save()
    User(name="Mr Praline", age=33, created_at=datetime(2021, 12, 1)).save()
    User(name="The colonel", age=90, created_at=datetime(2021, 12, 2)).save()
    User(name="Mr Creosote", age=21, created_at=datetime(2021, 12, 3)).save()
    User(name="Rabbit of Caerbannog", age=1, created_at=datetime(2021, 12, 4)).save()
    User(name="Gumbys", age=50, created_at=datetime(2021, 12, 4)).save()


@pytest.fixture(scope="function", autouse=True)
def clear_database(User):
    User.drop_collection()
    yield
    User.drop_collection()
