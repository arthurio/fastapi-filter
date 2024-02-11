[![pypi downloads](https://img.shields.io/pypi/dm/fastapi-filter?color=%232E73B2&logo=python&logoColor=%23F9D25F)](https://pypi.org/project/fastapi-filter)
[![codecov](https://codecov.io/gh/arthurio/fastapi-filter/branch/main/graph/badge.svg?token=I1DVBL1682)](https://codecov.io/gh/arthurio/fastapi-filter)
[![Netlify Status](https://api.netlify.com/api/v1/badges/83451c4f-76dd-4154-9b2d-61f654eb0704/deploy-status)](https://fastapi-filter.netlify.app/)
[![CodeQL](https://github.com/arthurio/fastapi-filter/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/arthurio/fastapi-filter/actions/workflows/codeql-analysis.yml)

# FastAPI filter

## Compatibility

**Required:**

- Python: >=3.9, <4.0
- Fastapi: >=0.100, <1.0
- Pydantic: >=2.0.0, <3.0.0

**Optional**

- MongoEngine: >=0.24.1, <0.28.0
- SQLAlchemy: >=1.4.36, <2.1.0

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

### Filter

https://user-images.githubusercontent.com/950449/176737541-0e36b72f-38e2-4368-abfa-8bbc0c82e8ae.mp4

### Order by

https://user-images.githubusercontent.com/950449/176747056-ea82d6b9-cb3b-43eb-aec7-96ba0bc79e8b.mp4

## Contribution

You can run tests with `pytest`.

```bash
pip install poetry
poetry install --extras all
pytest
```

<img width="884" alt="arthur_Arthurs-MacBook-Pro-2___code_fastapi-filter" src="https://user-images.githubusercontent.com/950449/176737623-a77f15d6-4e60-4c06-bdb7-b3d77f346a54.png">
