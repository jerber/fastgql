import typing as T
from uuid import UUID
from pydantic import TypeAdapter
from fastapi import FastAPI
from fastgql import GQL, GQLInterface, build_router
from .build_data import (
    accounts_by_username,
    content_by_person_id,
    content_by_id,
    shows_by_id,
)

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
