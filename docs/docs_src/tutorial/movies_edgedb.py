import json
import time
import typing as T
from uuid import UUID
import edgedb
from pydantic import TypeAdapter
from fastapi import FastAPI
from fastgql import GQL, GQLInterface, build_router
from dotenv import load_dotenv

load_dotenv()

edgedb_client = edgedb.create_async_client()

Contents = list[T.Union["Movie", "Show"]]


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


class Account(GQL):
    id: UUID
    username: str

    async def watchlist(self, limit: int) -> Contents:
        q = """select Account {
            watchlist: { id, title, release_year := [is Movie].release_year } limit <int64>$limit
        } filter .id = <uuid>$id"""
        account_d = await query_required_single_json(
            name="account.watchlist", query=q, id=self.id, limit=limit
        )
        return TypeAdapter(Contents).validate_python(account_d["watchlist"])


class Person(GQL):
    id: UUID
    name: str

    async def filmography(self) -> Contents:
        q = """select Person {
            filmography: { id, title, release_year := [is Movie].release_year }
        } filter .id = <uuid>$id"""
        person_d = await query_required_single_json(
            name="person.filmography", query=q, id=self.id
        )
        return TypeAdapter(Contents).validate_python(person_d["filmography"])


class Content(GQLInterface):
    id: UUID
    title: str

    async def actors(self) -> list["Person"]:
        q = """select Content { actors: { id, name } } filter .id = <uuid>$id"""
        content_d = await query_required_single_json(
            name="content.actors", query=q, id=self.id
        )
        return [Person(**p) for p in content_d["actors"]]


class Movie(Content):
    release_year: int


class Show(Content):
    async def seasons(self) -> list["Season"]:
        q = """select Show { season := .<show[is Season] { id, number } } filter .id = <uuid>$id"""
        show_d = await query_required_single_json(
            name="show.seasons", query=q, id=self.id
        )
        return [Season(**s) for s in show_d["season"]]

    async def num_seasons(self) -> int:
        q = """select Show { num_seasons } filter .id = <uuid>$id"""
        show_d = await query_required_single_json(
            name="show.num_seasons", query=q, id=self.id
        )
        return show_d["num_seasons"]


class Season(GQL):
    id: UUID
    number: int

    async def show(self) -> Show:
        q = """select Season { show: { id, title } } filter .id = <uuid>$id"""
        season_d = await query_required_single_json(
            name="season.show", query=q, id=self.id
        )
        return Show(**season_d["show"])


class Query(GQL):
    @staticmethod
    async def account_by_username(username: str) -> Account:
        q = """select Account { id, username } filter .username = <str>$username"""
        account_d = await query_required_single_json(
            name="account_by_username", query=q, username=username
        )
        return Account(**account_d)


router = build_router(query_models=[Query])

app = FastAPI()

app.include_router(router, prefix="/graphql")
