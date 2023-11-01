import json
import time
import typing as T
from uuid import UUID
import edgedb
from fastapi import FastAPI
from fastgql import (
    GQL,
    GQLInterface,
    build_router,
    Link,
    Property,
    get_qb,
    QueryBuilder,
    Depends,
    Info,
)
from dotenv import load_dotenv

load_dotenv()

edgedb_client = edgedb.create_async_client()

Contents = list[T.Union["Movie", "Show"]]


def parse_raw_content(raw_content: list[dict, T.Any]) -> Contents:
    w_list: Contents = []
    for item in raw_content:
        if item["typename"] == "default::Movie":
            w_list.append(Movie(**item["Movie"]))
        elif item["typename"] == "default::Show":
            w_list.append(Show(**item["Show"]))
        else:
            raise Exception(f"Invalid typename: {item=}")
    return w_list


async def query_required_single_json(
    name: str, query: str, **variables
) -> dict[str, T.Any]:
    start = time.time()
    res = json.loads(
        await edgedb_client.query_required_single_json(query=query, **variables)
    )
    took_ms = round((time.time() - start) * 1_000, 2)
    print(f"[{name}] took {took_ms} ms")
    return res


def update_watchlist(child_qb: QueryBuilder, limit: int) -> None:
    child_qb.set_limit(limit)


class Account(GQL):
    def __init__(self, **data):
        super().__init__(**data)
        self._data = data

    id: T.Annotated[UUID, Property(db_name="id")] = None
    username: T.Annotated[str, Property(db_name="username")] = None

    async def watchlist(
        self, info: Info, limit: int
    ) -> T.Annotated[Contents, Link(db_name="watchlist", update_qbs=update_watchlist)]:
        return parse_raw_content(raw_content=self._data[info.path[-1]])


class Content(GQLInterface):
    def __init__(self, **data):
        super().__init__(**data)
        self._data = data

    id: T.Annotated[UUID, Property(db_name="id")] = None
    title: T.Annotated[str, Property(db_name="title")] = None

    async def actors(
        self, info: Info
    ) -> T.Annotated[list["Person"], Link(db_name="actors")]:
        return [Person(**p) for p in self._data[info.path[-1]]]


class Movie(Content):
    release_year: T.Annotated[int, Property(db_name="release_year")] = None


class Show(Content):
    num_seasons: T.Annotated[int, Property(db_name="num_seasons")] = None

    async def seasons(
        self, info: Info
    ) -> T.Annotated[list["Season"], Link(db_name="<show[is Season]")]:
        return [Season(**s) for s in self._data[info.path[-1]]]


class Season(GQL):
    def __init__(self, **data):
        super().__init__(**data)
        self._data = data

    id: T.Annotated[UUID, Property(db_name="id")] = None
    number: T.Annotated[int, Property(db_name="number")] = None

    async def show(self, info: Info) -> T.Annotated[Show, Link(db_name="show")]:
        return Show(**self._data[info.path[-1]])


class Person(GQL):
    def __init__(self, **data):
        super().__init__(**data)
        self._data = data

    id: T.Annotated[UUID, Property(db_name="id")] = None
    name: T.Annotated[str, Property(db_name="name")] = None

    async def filmography(
        self, info: Info
    ) -> T.Annotated[Contents, Link(db_name="filmography")]:
        return parse_raw_content(raw_content=self._data[info.path[-1]])


class Query(GQL):
    @staticmethod
    async def account_by_username(
        username: str, qb: QueryBuilder = Depends(get_qb)
    ) -> Account:
        s, v = qb.build()
        q = f"""select Account {s} filter .username = <str>$username"""
        print(q)
        account_d = await query_required_single_json(
            name="account_by_username", query=q, username=username, **v
        )
        return Account(**account_d)


router = build_router(query_models=[Query])

app = FastAPI()

app.include_router(router, prefix="/graphql")
