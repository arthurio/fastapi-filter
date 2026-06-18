import nox


@nox.session(reuse_venv=True)
@nox.parametrize("sqlalchemy", ["2.0.51", "2.1.0"])
def tests(session, sqlalchemy):
    session.install(f"sqlalchemy=={sqlalchemy}")
    session.run("uv", "run", "pytest", *session.posargs, external=True)
