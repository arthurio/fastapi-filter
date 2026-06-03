import nox


@nox.session(python=["3.12", "3.13", "3.14"], reuse_venv=True)
@nox.parametrize("sqlalchemy", ["2.0.40"])
def tests(session, sqlalchemy):
    session.install(f"sqlalchemy=={sqlalchemy}")
    session.run("poetry", "run", "pytest", *session.posargs, external=True)
