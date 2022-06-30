[![pypi downloads](https://img.shields.io/pypi/dm/fastapi-filter?color=%232E73B2&logo=python&logoColor=%23F9D25F)](https://pypi.org/project/fastapi-filter)
[![codecov](https://codecov.io/gh/arthurio/fastapi-filter/branch/main/graph/badge.svg?token=I1DVBL1682)](https://codecov.io/gh/arthurio/fastapi-filter)
[![Netlify Status](https://api.netlify.com/api/v1/badges/83451c4f-76dd-4154-9b2d-61f654eb0704/deploy-status)](https://fastapi-filter.netlify.app/)

# FastAPI filter

## Compatibilty

**Required:**
  * Python: 3.10+
  * Fastapi: 0.78+
  * Pydantic: 1.9+
**Optional**
  * MongoEngine: 0.24.1+
  * SQLAlchemy: 1.4.36+

## Installation

```bash
# Basic version
pip install fastapi-filter

# With backends
pip install fastapi-filter[all]

# More selective
pip install fastapi-filter[sqlalchemy]
pip install fastapi-filter[mongoengine]
```

## Documentation

Please visit: [https://fastapi-filter.netlify.app/](https://fastapi-filter.netlify.app/)

## Examples

![Swagger UI](https://raw.githubusercontent.com/arthurio/fastapi-filter/main/docs/swagger-ui.png)

You can play with examples:

```bash
pip install poetry
poetry install
python examples/fastapi_filter_sqlalchemy.py
```

## Contribution

You can run tests with `pytest`.

```bash
pip install poetry
poetry install --extras all
pytest
```
