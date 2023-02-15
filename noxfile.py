import nox


@nox.session(reuse_venv=True)
@nox.parametrize("sqlalchemy", ["1.4.46", "2.0.3"])
def tests(session, sqlalchemy):
    session.install(f"sqlalchemy=={sqlalchemy}")
    session.run("poetry", "run", "pytest", *session.posargs, external=True)
