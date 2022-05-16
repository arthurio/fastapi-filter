import os
from datetime import datetime

import pytest
import sqlalchemy_utils
from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="session")
def sqlite_file():
    file_name = "./fastapi_filter.sqlite"
    yield file_name
    os.remove(file_name)


@pytest.fixture(scope="session")
def database_url(sqlite_file) -> str:
    return f"sqlite:///{sqlite_file}"


@pytest.fixture(scope="session")
def engine(database_url):
    return create_engine(database_url)


@pytest.fixture(scope="session")
def SessionLocal(engine, create_test_database):
    return sessionmaker(autocommit=True, autoflush=True, bind=engine)


@pytest.fixture(scope="function")
def session(engine, SessionLocal, Base):
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="session")
def create_test_database(engine):
    if sqlalchemy_utils.database_exists(engine.url):
        sqlalchemy_utils.drop_database(engine.url)
    sqlalchemy_utils.create_database(engine.url)
    yield


@pytest.fixture(scope="session")
def Base(engine):
    return declarative_base(bind=engine)


@pytest.fixture(scope="session")
def User(Base):
    class User(Base):
        __tablename__ = "users"

        object_id = Column(Integer, primary_key=True, autoincrement=True)
        created_at = Column(DateTime, default=datetime.now)
        updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
        name = Column(String, nullable=True)
        age = Column(Integer, nullable=False, default=21)

    return User


@pytest.fixture(scope="function")
def users(session, User):
    session.add_all(
        [
            User(name=None, age=21, created_at=datetime(2021, 12, 1)),
            User(name="Arthur", age=33, created_at=datetime(2021, 12, 1)),
            User(name="Ranjith", age=90, created_at=datetime(2021, 12, 2)),
            User(name="Christina", age=21, created_at=datetime(2021, 12, 3)),
            User(name="Nick", age=1, created_at=datetime(2021, 12, 4)),
            User(name="Akash", age=50, created_at=datetime(2021, 12, 4)),
        ]
    )
