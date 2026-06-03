import nox


@nox.session(reuse_venv=True)
@nox.parametrize("sqlalchemy", ["2.0.40"])
def tests(session, sqlalchemy):
    session.install(f"sqlalchemy=={sqlalchemy}")
    session.run("poetry", "run", "pytest", *session.posargs, external=True)
