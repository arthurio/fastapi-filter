import nox


@nox.session(reuse_venv=True)
@nox.parametrize("sqlalchemy", ["2.0.51"])  # add "2.1.0" once the final release is on PyPI
def tests(session, sqlalchemy):
    # Install the project with all optional extras into the nox session venv
    session.install(".[all]")
    # Install test/dev dependencies directly into the nox session venv
    session.install(
        "pytest>=9.0.0",
        "pytest-asyncio>=1.4.0",
        "pytest-cov>=5.0.0",
        "httpx>=0.28.0",
        "aiosqlite>=0.20.0",
        "Faker>=26.0.0",
        "SQLAlchemy-Utils>=0.41.2",
        "uvicorn>=0.30.1",
    )
    # Override SQLAlchemy with the specific version under test so the nox parametrization
    # actually exercises the pinned version (not the uv.lock-resolved version).
    session.install(f"sqlalchemy[asyncio]=={sqlalchemy}")
    session.run("pytest", *session.posargs)
