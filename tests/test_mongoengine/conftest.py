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
    User(name=None, age=21, created_at=datetime.fromisoformat("2021-12-01")).save()
    User(name="Arthur", age=33, created_at=datetime.fromisoformat("2021-12-01")).save()
    User(name="Ranjith", age=90, created_at=datetime.fromisoformat("2021-12-02")).save()
    User(name="Christina", age=21, created_at=datetime.fromisoformat("2021-12-03")).save()
    User(name="Nick", age=1, created_at=datetime.fromisoformat("2021-12-04")).save()
    User(name="Akash", age=50, created_at=datetime.fromisoformat("2021-12-04")).save()


@pytest.fixture(scope="function", autouse=True)
def clear_database(User):
    User.drop_collection()
    yield
    User.drop_collection()
