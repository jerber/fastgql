import typing as T
from uuid import UUID, uuid4
from pydantic import TypeAdapter
from fastapi import FastAPI
from fastgql import GQL, GQLInterface, build_router

people = [
    {"id": uuid4(), "name": "Margot Robbie"},
    {"id": uuid4(), "name": "Ryan Gosling"},
    {"id": uuid4(), "name": "Jeremy Allen White"},
]
movies = [
    {"id": uuid4(), "title": "Barbie", "release_year": 2023, "actors": people[0:2]}
]
shows = [
    {
        "id": uuid4(),
        "title": "Game Of Thrones",
        "seasons": [{"id": uuid4(), "number": x} for x in range(1, 9)],
        "actors": people[2:],
    }
]
content = [*movies, *shows]
content_by_person_id = {}
for p in people:
    person_id = p["id"]
    filmography = []
    for c in content:
        if person_id in [c_actor["id"] for c_actor in c["actors"]]:
            filmography.append(c)
    content_by_person_id[person_id] = filmography
movies_by_id: dict[UUID, dict] = {m["id"]: m for m in movies}
shows_by_id: dict[UUID, dict] = {s["id"]: s for s in shows}
content_by_id: dict[UUID, dict] = {c["id"]: c for c in content}
accounts = [{"id": uuid4(), "username": "jeremy", "watchlist": content}]
accounts_by_username = {a["username"]: a for a in accounts}

Contents = list[T.Union["Movie", "Show"]]


class Account(GQL):
    id: UUID
    username: str

    def watchlist(self) -> Contents:
        """create a list of movies and shows"""
        watchlist_raw = accounts_by_username[self.username]["watchlist"]
        return TypeAdapter(Contents).validate_python(watchlist_raw)


class Person(GQL):
    id: UUID
    name: str

    def filmography(self) -> Contents:
        return TypeAdapter(Contents).validate_python(content_by_person_id[self.id])


class Content(GQLInterface):
    id: UUID
    title: str

    def actors(self) -> list["Person"]:
        return [Person(**p) for p in content_by_id[self.id]["actors"]]


class Movie(Content):
    id: UUID
    release_year: int


class Show(Content):
    id: UUID

    def seasons(self) -> list["Season"]:
        return [Season(**s) for s in shows_by_id[self.id]["seasons"]]

    def num_seasons(self) -> int:
        return len(self.seasons())


class Season(GQL):
    id: UUID
    number: int
    show: "Show"


class Query(GQL):
    @staticmethod
    async def account_by_username(username: str) -> Account:
        account = accounts_by_username[username]
        return Account(**account)


router = build_router(query_models=[Query])

app = FastAPI()

app.include_router(router, prefix="/graphql")
