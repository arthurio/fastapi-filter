"""End-to-end tests of the example apps (sqlalchemy, mongoengine, beanie) over real HTTP."""

import os
import subprocess  # nosec B404
import sys
import tempfile
import time

import pytest
import requests

REPO = os.environ.get("FF_REPO") or os.path.join(os.environ.get("WORKSPACE_DIR", "/l2l/workspace"), "fastapi-filter")
PY = sys.executable
PORTS = {"sqlalchemy": 8101, "mongoengine": 8102, "beanie": 8103}


@pytest.fixture(scope="module", params=list(PORTS))
def base(request):
    name = request.param
    port = PORTS[name]
    p = subprocess.Popen(  # nosec B603
        [
            PY,
            "-m",
            "uvicorn",
            f"fastapi_filter_{name}:app",
            "--port",
            str(port),
            "--app-dir",
            os.path.join(REPO, "examples"),
        ],
        cwd=__import__("tempfile").mkdtemp(),  # keep repo source off sys.path so the installed wheel is used
        env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            try:
                if requests.get(url + "/docs", timeout=2).status_code == 200:
                    break
            except requests.RequestException:
                time.sleep(0.5)
        else:
            pytest.fail("app did not start")
        yield url
    finally:
        p.terminate()
        p.wait(10)


def is_sqlalchemy(base):
    return base.endswith(f":{PORTS['sqlalchemy']}")


def users(base, **p):
    return requests.get(base + "/users", params={"age__gte": 0, **p}, timeout=10)


def test_list_users(base):
    r = users(base)
    assert r.status_code == 200 and len(r.json()) == 100
    assert {"name", "email", "age", "address"} <= set(r.json()[0])
    assert "id" in r.json()[0] or "_id" in r.json()[0]


def test_default_order_age_asc(base):
    ages = [u["age"] for u in users(base).json()]
    assert ages == sorted(ages)


def test_order_desc(base):
    ages = [u["age"] for u in users(base, order_by="-age").json()]
    assert ages == sorted(ages, reverse=True)


def test_range_filter(base):
    r = users(base, age__gte=30, age__lt=50)
    assert r.status_code == 200
    assert all(30 <= u["age"] < 50 for u in r.json())


def test_name_filters_and_search(base):
    first = users(base).json()[0]["name"]
    r = users(base, name=first)
    assert r.status_code == 200 and r.json() and all(u["name"] == first for u in r.json())
    if is_sqlalchemy(base):  # only the sqlalchemy example exposes neq/ilike
        r = users(base, name__neq=first)
        assert r.status_code == 200 and all(u["name"] != first for u in r.json())
    tok = first.split()[0]
    r = users(base, search=tok.lower())
    assert r.status_code == 200 and r.json() and all(tok.lower() in u["name"].lower() for u in r.json())
    if is_sqlalchemy(base):
        r = users(base, name__ilike="%" + tok.upper() + "%")
        assert r.status_code == 200 and r.json()


def test_nested_address_filter(base):
    city = users(base).json()[0]["address"]["city"]
    r = users(base, address__city=city)
    assert r.status_code == 200 and r.json()
    assert all(u["address"]["city"] == city for u in r.json())


def test_addresses_list(base):
    r = requests.get(base + "/addresses", timeout=10)
    assert r.status_code == 200 and len(r.json()) == 100


def test_missing_required(base):
    assert requests.get(base + "/users", timeout=10).status_code == 422


def test_invalid_type(base):
    assert users(base, age__lt="abc").status_code == 422


def test_invalid_order_field(base):
    assert users(base, order_by="nonexistent").status_code in (400, 422)


def test_imports_from_installed_wheel():
    out = subprocess.run(  # nosec B603
        [PY, "-I", "-c", "import fastapi_filter,sys;print(fastapi_filter.__file__)"],
        cwd=tempfile.gettempdir(),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert out.returncode == 0, out.stderr
    assert "site-packages" in out.stdout
