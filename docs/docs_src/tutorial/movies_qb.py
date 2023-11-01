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
    node_from_path,
)
from dotenv import load_dotenv

load_dotenv()

edgedb_client = edgedb.create_async_client()

Contents = list[T.Union["Movie", "Show"]]


def parse_raw_content(raw_content: list[dict, T.Any]) -> Contents:
    w_list: Contents = []
    for item in raw_content:
        if item["typename"] == "default::Movie":
            if movie := item.get('Movie'):
                w_list.append(Movie(**movie))
        elif item["typename"] == "default::Show":
            if show := item.get('Show'):
                w_list.append(Show(**show))
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


class AccountPageInfo(GQL):
    has_next_page: bool
    has_previous_page: bool
    start_cursor: str | None
    end_cursor: str | None


class AccountEdge(GQL):
    cursor: str
    node: "Account"


class AccountConnection(GQL):
    page_info: AccountPageInfo
    edges: list[AccountEdge]
    total_count: int


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


AccountEdge.model_rebuild()


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

    @staticmethod
    async def account_connection(
        info: Info,
        *,
        before: str | None = None,
        after: str | None = None,
        first: int,
    ) -> AccountConnection:
        qb: QueryBuilder = await Account.qb_config.from_info(
            info=info, node=node_from_path(node=info.node, path=["edges", "node"])
        )
        qb.fields.add("username")
        variables = {"first": first}
        filter_list: list[str] = []
        if before:
            filter_list.append(".username > <str>$before")
            variables["before"] = before
        if after:
            filter_list.append(".username < <str>$after")
            variables["after"] = after
        if filter_list:
            filter_s = f'filter {" and ".join(filter_list)} '
        else:
            filter_s = ""
        qb.add_variables(variables, replace=False)
        s, v = qb.build()
        q = f"""
        with
            all_accounts := (select Account),
            _first := <int16>$first,
            accounts := (select all_accounts {filter_s}order by .username desc limit _first),
        select {{
            total_count := count(all_accounts),
            accounts := accounts {s}
        }}
        """
        connection_d = await query_required_single_json(
            name="account_connection", query=q, **v
        )
        total_count = connection_d["total_count"]
        _accounts = [Account(**d) for d in connection_d["accounts"]]
        connection = AccountConnection(
            page_info=AccountPageInfo(
                has_next_page=len(_accounts) == first and total_count > first,
                has_previous_page=after is not None,
                start_cursor=_accounts[0].username if _accounts else None,
                end_cursor=_accounts[-1].username if _accounts else None,
            ),
            total_count=total_count,
            edges=[
                AccountEdge(node=account, cursor=account.username)
                for account in _accounts
            ],
        )
        return connection


router = build_router(query_models=[Query])

app = FastAPI()

app.include_router(router, prefix="/graphql")
