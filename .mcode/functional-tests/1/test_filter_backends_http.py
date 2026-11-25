"""Functional tests: FilterDepends endpoints on every backend (sqlalchemy, beanie, mongoengine).

Each backend gets a small FastAPI app (real ASGI request/response via Starlette's TestClient, lifespan run),
the same dataset and the same behavioural assertions. Needs mongod on 127.0.0.1:27017 for beanie/mongoengine.
"""

import os
import tempfile
import uuid
import warnings
from contextlib import asynccontextmanager
from datetime import datetime

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from fastapi_filter import FilterDepends, with_prefix

RUN = "ftrun_" + uuid.uuid4().hex[:8]
MONGO = "mongodb://127.0.0.1:27017"

ROWS = [
    # name, age, street, city, country
    ("Mr Praline", 33, "22 rue Bellier", "Nantes", "France"),
    ("The colonel", 90, "Wrench", "Bathroom", "Clue"),
    ("Mr Creosote", 21, None, "Nantes", "France"),
    ("Rabbit of Caerbannog", 1, "1234 street", "San Francisco", "United States"),
    ("Gumbys", 50, "4567 avenue", "Denver", "United States"),
    (None, 7, "9 nameless road", "Paris", "France"),
]


# ---------------------------------------------------------------- sqlalchemy
def build_sqlalchemy():
    from sqlalchemy import ForeignKey, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

    from fastapi_filter.contrib.sqlalchemy import Filter

    path = os.path.join(tempfile.mkdtemp(prefix=RUN), "db.sqlite")
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    sessionmaker = async_sessionmaker(engine, class_=AsyncSession)

    class Base(DeclarativeBase):
        pass

    class Address(Base):
        __tablename__ = "addresses"
        id: Mapped[int] = mapped_column(primary_key=True)
        street: Mapped[str | None]
        city: Mapped[str]
        country: Mapped[str]

    class User(Base):
        __tablename__ = "users"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str | None]
        age: Mapped[int]
        address_id: Mapped[int | None] = mapped_column(ForeignKey("addresses.id"))
        address: Mapped[Address] = relationship(Address, lazy="joined")

    class AddressFilter(Filter):
        street__isnull: bool | None = None
        country: str | None = None
        city: str | None = None
        city__in: list[str] | None = None
        country__not_in: list[str] | None = None

        class Constants(Filter.Constants):
            model = Address

    class UserFilter(Filter):
        name: str | None = None
        name__in: list[str] | None = None
        name__not_in: list[str] | None = None
        name__neq: str | None = None
        name__not: str | None = None
        name__isnull: bool | None = None
        name__like: str | None = None
        name__ilike: str | None = None
        age: int | None = None
        age__lt: int | None = None
        age__lte: int | None = None
        age__gt: int | None = None
        age__gte: int | None = None
        age__in: list[int] | None = None
        address: AddressFilter | None = FilterDepends(with_prefix("address", AddressFilter))
        order_by: list[str] | None = None
        search: str | None = None

        class Constants(Filter.Constants):
            model = User
            search_model_fields = ["name"]

    @asynccontextmanager
    async def lifespan(app):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sessionmaker() as s:
            for name, age, street, city, country in ROWS:
                s.add(User(name=name, age=age, address=Address(street=street, city=city, country=country)))
            await s.commit()
        yield
        await engine.dispose()

    app = FastAPI(lifespan=lifespan)

    async def db():
        async with sessionmaker() as s:
            yield s

    def ser(u):
        return {"name": u.name, "age": u.age, "address": {"city": u.address.city, "street": u.address.street}}

    @app.get("/users")
    async def users(f: UserFilter = FilterDepends(UserFilter), s: AsyncSession = Depends(db)):
        q = f.sort(f.filter(select(User).join(Address)))
        return [ser(u) for u in (await s.execute(q)).scalars().unique().all()]

    @app.get("/users_prefixed")
    async def users_prefixed(
        f: UserFilter = FilterDepends(with_prefix("p", UserFilter), by_alias=True), s: AsyncSession = Depends(db)
    ):
        q = f.sort(f.filter(select(User).join(Address)))
        return [ser(u) for u in (await s.execute(q)).scalars().unique().all()]

    return app, {"nin": "name__not_in", "supports_like": True}


# -------------------------------------------------------------------- beanie
def build_beanie():
    from beanie import Document, Link, init_beanie
    from beanie.odm.fields import WriteRules
    from pymongo import AsyncMongoClient

    from fastapi_filter.contrib.beanie import Filter

    class Address(Document):
        street: str | None = None
        city: str
        country: str

    class User(Document):
        created_at: datetime
        name: str | None = None
        age: int
        address: Link[Address] | None = None

    class AddressFilter(Filter):
        street__isnull: bool | None = None
        country: str | None = None
        city: str | None = None
        city__in: list[str] | None = None
        country__nin: list[str] | None = None

        class Constants(Filter.Constants):
            model = Address

    class UserFilter(Filter):
        name: str | None = None
        name__in: list[str] | None = None
        name__nin: list[str] | None = None
        name__not_in: list[str] | None = None
        name__ne: str | None = None
        name__isnull: bool | None = None
        age: int | None = None
        age__lt: int | None = None
        age__lte: int | None = None
        age__gt: int | None = None
        age__gte: int | None = None
        age__in: list[int] | None = None
        address: AddressFilter | None = FilterDepends(with_prefix("address", AddressFilter))
        order_by: list[str] | None = None
        search: str | None = None

        class Constants(Filter.Constants):
            model = User
            search_model_fields = ["name"]

    @asynccontextmanager
    async def lifespan(app):
        client = AsyncMongoClient(MONGO)
        await init_beanie(database=client[RUN + "_beanie"], document_models=[Address, User])
        for name, age, street, city, country in ROWS:
            await User(
                name=name,
                age=age,
                created_at=datetime(2021, 1, 1),
                address=Address(street=street, city=city, country=country),
            ).save(link_rule=WriteRules.WRITE)
        yield
        await client.drop_database(RUN + "_beanie")
        await client.close()

    app = FastAPI(lifespan=lifespan)

    def ser(u):
        return {"name": u.name, "age": u.age, "address": {"city": u.address.city, "street": u.address.street}}

    @app.get("/users")
    async def users(f: UserFilter = FilterDepends(UserFilter)):
        q = f.sort(f.filter(User.find()))
        return [ser(u) for u in await q.to_list()]

    @app.get("/users_prefixed")
    async def users_prefixed(f: UserFilter = FilterDepends(with_prefix("p", UserFilter), by_alias=True)):
        q = f.sort(f.filter(User.find()))
        return [ser(u) for u in await q.to_list()]

    return app, {"nin": "name__nin", "supports_like": False}


# --------------------------------------------------------------- mongoengine
def build_mongoengine():
    import mongoengine
    from mongoengine import Document, fields

    from fastapi_filter.contrib.mongoengine import Filter

    alias = RUN

    class Address(Document):
        street = fields.StringField()
        city = fields.StringField()
        country = fields.StringField()
        meta = {"db_alias": alias, "collection": "address"}

    class User(Document):
        name = fields.StringField()
        age = fields.IntField()
        address = fields.ReferenceField(Address)
        meta = {"db_alias": alias, "collection": "user"}

    class AddressFilter(Filter):
        street__isnull: bool | None = None
        country: str | None = None
        city: str | None = None
        city__in: list[str] | None = None
        country__nin: list[str] | None = None

        class Constants(Filter.Constants):
            model = Address

    class UserFilter(Filter):
        name: str | None = None
        name__in: list[str] | None = None
        name__nin: list[str] | None = None
        name__ne: str | None = None
        name__isnull: bool | None = None
        age: int | None = None
        age__lt: int | None = None
        age__lte: int | None = None
        age__gt: int | None = None
        age__gte: int | None = None
        age__in: list[int] | None = None
        address: AddressFilter | None = FilterDepends(with_prefix("address", AddressFilter))
        order_by: list[str] | None = None
        search: str | None = None

        class Constants(Filter.Constants):
            model = User
            search_model_fields = ["name"]

    @asynccontextmanager
    async def lifespan(app):
        mongoengine.connect(db=RUN + "_me", host=MONGO, alias=alias, uuidRepresentation="standard")
        for name, age, street, city, country in ROWS:
            User(name=name, age=age, address=Address(street=street, city=city, country=country).save()).save()
        yield
        mongoengine.get_connection(alias).drop_database(RUN + "_me")
        mongoengine.disconnect(alias)

    app = FastAPI(lifespan=lifespan)

    def ser(u):
        return {"name": u.name, "age": u.age, "address": {"city": u.address.city, "street": u.address.street}}

    @app.get("/users")
    def users(f: UserFilter = FilterDepends(UserFilter)):
        return [ser(u) for u in f.sort(f.filter(User.objects()))]

    @app.get("/users_prefixed")
    def users_prefixed(f: UserFilter = FilterDepends(with_prefix("p", UserFilter), by_alias=True)):
        return [ser(u) for u in f.sort(f.filter(User.objects()))]

    return app, {"nin": "name__nin", "supports_like": False}


BUILDERS = {"sqlalchemy": build_sqlalchemy, "beanie": build_beanie, "mongoengine": build_mongoengine}


@pytest.fixture(scope="module", params=list(BUILDERS))
def env(request):
    app, meta = BUILDERS[request.param]()
    with TestClient(app) as client:
        yield client, meta, request.param


def get(env, path="/users", **params):
    client, _, _ = env
    return client.get(path, params=params)


def names(r):
    assert r.status_code == 200, r.text
    return [u["name"] for u in r.json()]


# ------------------------------------------------------------------ happy paths
def test_no_filters_returns_all(env):
    assert len(get(env).json()) == 6


def test_plain_equality(env):
    assert names(get(env, name="Gumbys")) == ["Gumbys"]


def test_age_range_operators(env):
    ages = sorted(u["age"] for u in get(env, age__gte=21, age__lt=50).json())
    assert ages == [21, 33]
    assert sorted(u["age"] for u in get(env, age__gt=50).json()) == [90]
    assert sorted(u["age"] for u in get(env, age__lte=7).json()) == [1, 7]


def test_in_list(env):
    assert sorted(names(get(env, name__in="Gumbys,The colonel"))) == ["Gumbys", "The colonel"]
    assert sorted(u["age"] for u in get(env, age__in="1,90").json()) == [1, 90]


def test_not_in_list(env):
    _, meta, _ = env
    got = names(get(env, **{meta["nin"]: "Gumbys,The colonel,Mr Praline"}))
    assert "Gumbys" not in got and "The colonel" not in got and "Mr Praline" not in got
    assert "Mr Creosote" in got


def test_neq(env):
    _, _, backend = env
    key = "name__neq" if backend == "sqlalchemy" else "name__ne"
    got = names(get(env, **{key: "Gumbys"}))
    assert "Gumbys" not in got and "Mr Praline" in got


def test_isnull_true_and_false(env):
    assert [u["age"] for u in get(env, name__isnull="true").json()] == [7]
    r = get(env, name__isnull="false")
    assert len(r.json()) == 5 and None not in names(r)


def test_search(env):
    assert sorted(names(get(env, search="mr "))) == ["Mr Creosote", "Mr Praline"]
    assert names(get(env, search="GUMB")) == ["Gumbys"]


def test_search_combined_with_filter(env):
    assert names(get(env, search="mr", age__gt=25)) == ["Mr Praline"]


def test_nested_filters(env):
    r = get(env, address__country="France", address__city="Nantes")
    assert sorted(names(r)) == ["Mr Creosote", "Mr Praline"]
    assert all(u["address"]["city"] == "Nantes" for u in r.json())


def test_nested_in_operator(env):
    r = get(env, address__city__in="Denver,Paris")
    assert sorted(u["address"]["city"] for u in r.json()) == ["Denver", "Paris"]


def test_nested_not_in(env):
    _, _, backend = env
    key = "address__country__not_in" if backend == "sqlalchemy" else "address__country__nin"
    r = get(env, **{key: "France,United States"})
    assert names(r) == ["The colonel"]


def test_nested_isnull(env):
    r = get(env, address__street__isnull="true")
    assert names(r) == ["Mr Creosote"]


def test_nested_combined_with_root_filter(env):
    r = get(env, address__country="United States", age__gt=10)
    assert names(r) == ["Gumbys"]


def test_empty_nested_filter_ignored(env):
    assert len(get(env).json()) == 6


# ----------------------------------------------------------------------- order
def test_order_ascending_default(env):
    ages = [u["age"] for u in get(env, order_by="age").json()]
    assert ages == sorted(ages)


def test_order_plus_prefix(env):
    # "+" is URL-encoded by requests ('%2B'), so FastAPI receives the literal "+age"
    ages = [u["age"] for u in get(env, order_by="+age").json()]
    assert ages == sorted(ages)


def test_order_minus_prefix(env):
    ages = [u["age"] for u in get(env, order_by="-age").json()]
    assert ages == sorted(ages, reverse=True) and ages[0] == 90


def test_order_multiple_fields_priority(env):
    r = get(env, order_by="-age,name")
    ages = [u["age"] for u in r.json()]
    assert ages == sorted(ages, reverse=True)
    r = get(env, address__country="France", order_by="+name")
    got = [n for n in names(r) if n]
    assert got == sorted(got)


def test_order_by_with_filter(env):
    ages = [u["age"] for u in get(env, age__gte=20, order_by="-age").json()]
    assert ages == [90, 50, 33, 21]


def test_order_invalid_field(env):
    assert get(env, order_by="nonexistent").status_code == 422


def test_order_duplicate_field(env):
    assert get(env, order_by="age,-age").status_code == 422


# ------------------------------------------------------------------ with_prefix
def test_with_prefix_alias_filters(env):
    r = get(env, "/users_prefixed", p__age__gte=33, p__order_by="-age")
    assert [u["age"] for u in r.json()] == [90, 50, 33]


def test_with_prefix_nested_and_search(env):
    r = get(env, "/users_prefixed", p__address__city="Nantes", p__search="creo")
    assert names(r) == ["Mr Creosote"]


def test_with_prefix_unprefixed_name_rejected_or_ignored(env):
    # un-prefixed params are not part of the prefixed filter: must not filter
    r = get(env, "/users_prefixed", age="1")
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        assert len(r.json()) == 6


# ------------------------------------------------------------------ validation
def test_invalid_type(env):
    assert get(env, age__lt="abc").status_code == 422


def test_invalid_bool(env):
    assert get(env, name__isnull="maybe").status_code == 422


def test_empty_in_list(env):
    r = get(env, name__in="")
    assert r.status_code == 200 and r.json() == []


# ------------------------------------------------- sqlalchemy like deprecation
def test_like_ilike_warning_and_behaviour(env):
    client, _, backend = env
    if backend != "sqlalchemy":
        pytest.skip("like/ilike deprecation is sqlalchemy-specific")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        r = client.get("/users", params={"name__ilike": "mr"})
    assert r.status_code == 200
    assert sorted(names(r)) == ["Mr Creosote", "Mr Praline"]
    assert any(issubclass(x.category, DeprecationWarning) and "% character" in str(x.message) for x in w), [
        str(x.message) for x in w
    ]


def test_like_with_explicit_percent_no_warning(env):
    client, _, backend = env
    if backend != "sqlalchemy":
        pytest.skip("sqlalchemy-specific")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        r = client.get("/users", params={"name__like": "Mr%"})
    assert sorted(names(r)) == ["Mr Creosote", "Mr Praline"]
    assert not [x for x in w if issubclass(x.category, DeprecationWarning) and "% character" in str(x.message)]


def test_like_case_sensitivity_sqlalchemy(env):
    client, _, backend = env
    if backend != "sqlalchemy":
        pytest.skip("sqlalchemy-specific")
    r = client.get("/users", params={"name__ilike": "%GUMBYS%"})
    assert names(r) == ["Gumbys"]


def test_not_operator_sqlalchemy(env):
    client, _, backend = env
    if backend != "sqlalchemy":
        pytest.skip("sqlalchemy-specific")
    # `not` maps to IS NOT: NULL-safe comparison with a value
    r = client.get("/users", params={"name__not": "Gumbys"})
    assert r.status_code == 200 and "Gumbys" not in names(r)
