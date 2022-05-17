import os
from datetime import datetime

import pytest
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker


@pytest.fixture(scope="session")
def sqlite_file():
    file_name = "./fastapi_filter_test.sqlite"
    yield file_name
    os.remove(file_name)


@pytest.fixture(scope="session")
def database_url(sqlite_file) -> str:
    return f"sqlite+aiosqlite:///{sqlite_file}"


@pytest.fixture(scope="session")
def engine(database_url):
    return create_async_engine(database_url)


@pytest.fixture(scope="session")
def SessionLocal(engine):
    return sessionmaker(autoflush=True, bind=engine, class_=AsyncSession)


@pytest.fixture(scope="function")
async def session(engine, SessionLocal, Base):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="session")
def Base(engine):
    return declarative_base(bind=engine)


@pytest.fixture(scope="session")
def User(Base, Address):
    class User(Base):
        __tablename__ = "users"

        id = Column(Integer, primary_key=True, autoincrement=True)
        created_at = Column(DateTime, default=datetime.now)
        updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
        name = Column(String, nullable=True)
        age = Column(Integer, nullable=False)
        address_id = Column(Integer, ForeignKey("addresses.id"), nullable=True)
        address: Address = relationship(Address, backref="users", lazy="joined")

    return User


@pytest.fixture(scope="session")
def Address(Base):
    class Address(Base):
        __tablename__ = "addresses"

        id = Column(Integer, primary_key=True, autoincrement=True)
        street = Column(String, nullable=True)
        city = Column(String, nullable=False)
        country = Column(String, nullable=False)

    return Address


@pytest.fixture(scope="function")
async def users(session, User, Address):
    session.add_all(
        [
            User(
                name=None,
                age=21,
                created_at=datetime(2021, 12, 1),
            ),
            User(
                name="Mr Praline",
                age=33,
                created_at=datetime(2021, 12, 1),
                address=Address(street="22 rue Bellier", city="Nantes", country="France"),
            ),
            User(
                name="The colonel",
                age=90,
                created_at=datetime(2021, 12, 2),
                address=Address(street="Wrench", city="Bathroom", country="Clue"),
            ),
            User(
                name="Mr Creosote",
                age=21,
                created_at=datetime(2021, 12, 3),
                address=Address(city="Nantes", country="France"),
            ),
            User(
                name="Rabbit of Caerbannog",
                age=1,
                created_at=datetime(2021, 12, 4),
                address=Address(street="1234 street", city="San Francisco", country="United States"),
            ),
            User(
                name="Gumbys",
                age=50,
                created_at=datetime(2021, 12, 4),
                address=Address(street="4567 avenue", city="Denver", country="United States"),
            ),
        ]
    )
    await session.commit()
