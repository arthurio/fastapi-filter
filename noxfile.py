import nox


@nox.session(reuse_venv=True, python=["3.11", "3.12", "3.13", "3.14", "3.15"])
@nox.parametrize("sqlalchemy", ["2.0.58", "2.1.0"])
def tests(session, sqlalchemy):
    session.run("poetry", "install", "--extras", "all", external=True)
    session.install(f"sqlalchemy=={sqlalchemy}")
    session.run("poetry", "run", "pytest", *session.posargs, external=True)
