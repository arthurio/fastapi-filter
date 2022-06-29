# FastAPI Filter

Add querystring filters to your api endpoints and show them in the swagger UI.

The supported backends are [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) and [MongoEngine](https://github.com/MongoEngine/mongoengine).


## Example

![Swagger UI](./swagger-ui.png)

## Filter

Based on the type of orm/odb you use there might be some slightly different setup for your classes (e.g. `collection` vs. `model` in the `Config` class of the filter). But the bottom line is defining the fields you want to filter on and the type of operator you want, then tie your filter to a specific model/collection.

### Examples

[SQLAlchemy](https://github.com/arthurio/fastapi-filter/blob/main/examples/fastapi_filter_sqlalchemy.py)

[MongoEngine](https://github.com/arthurio/fastapi-filter/blob/main/examples/fastapi_filter_mongoengine.py)

### Operators

By default, fastapi_filter supports the following operators:
  - `gt`
  - `gte`
  - `in`
  - `isnull`
  - `it`
  - `lte`
  - `not`
  - `not_in`

_**Note:** Mysql excludes `None` values when using `in` filter)_

For the list related operators (`in`, `not_in`), simply pass a comma separated list of strings to your api endpoint and
they will be converted into the list of the type you defined.

For example, if the filter field is `age__in`, you can send `?age__in=1,3,5,7,9`.

### Related fields

As long as you setup your query to join your related models, it's pretty straightforward to add related field filters
and even re-use existing filters for their models.

As you can see in the examples, all it takes is something along the lines of:

```python hl_lines="19"
class AddressFilter(Filter):
    street: str | None
    country: str | None
    city__in: list[str] | None

    class Constants:
        model = Address


class UserFilter(Filter):
    name: str | None
    address: AddressFilter | None = FilterDepends(with_prefix("address", AddressFilter))

    class Constants:
        model = User

@app.get("/users", response_model=list[UserOut])
async def get_users(user_filter: UserFilter = FilterDepends(UserFilter), db: AsyncSession = Depends(get_db)) -> Any:
    query = user_filter.filter(select(User).outerjoin(Address))   # (1)
    result = await db.execute(query)
    return result.scalars().all()
```

1. See how we need to join with the Address model to be able to filter on it?

The `with_prefix` wrapper function sets the prefix for your filters, so in that example you would use
`?address__city_in=Nantes,Boston` for example.

### FilterDepends

[link](https://github.com/arthurio/fastapi-filter/blob/main/fastapi_filter/base/filter.py#L87)

Wherever you would use a `Depends`, replace it with `FilterDepends` if you are passing a filter class. The reason is
that `FilterDepends` converts the `list` filter fields to `str` so that they can be displayed and used in swagger.


### with_prefix

[link](https://github.com/arthurio/fastapi-filter/blob/main/fastapi_filter/base/filter.py#L21)

This is a utility function that will take an existing filter and prefix all its fields with a given value. It's mostly
used for filtering related fields.

The following would be equivalent:

```python
class AddressFilter(Filter):
    street: str | None
    country: str | None

    class Constants:
        model = Address


class UserFilter(Filter):
    name: str | None
    address: AddressFilter | None = FilterDepends(with_prefix("address", AddressFilter))

    class Constants:
        model = User
```

AND

```python
class UserFilter(Filter):
    name: str | None
    address__street: str | None
    address__country: str | None
```

## Order by
