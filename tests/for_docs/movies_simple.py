from uuid import UUID, uuid4
from fastapi import FastAPI
from fastgql import GQL, build_router


class Account(GQL):  # (4)!
    id: UUID
    username: str

    def watchlist(self) -> list["Movie"]:  # (1)!
        # Usually we'd use a database to get the user's watchlist. For this example, it is hardcoded.
        return [
            Movie(id=uuid4(), title="Barbie", release_year=2023),
            Movie(id=uuid4(), title="Oppenheimer", release_year=2023),
        ]

    def _secret_function(self) -> str:  # (2)!
        return "this is not exposed!"


class Person(GQL):
    id: UUID
    name: str

    def filmography(self) -> list["Movie"]:
        return [
            Movie(id=uuid4(), title="Barbie", release_year=2023),
            Movie(id=uuid4(), title="Wolf of Wallstreet", release_year=2013),
        ]


class Movie(GQL):
    id: UUID
    title: str
    release_year: int

    def actors(self) -> list["Person"]:
        return [
            Person(id=uuid4(), name="Margot Robbie"),
            Person(id=uuid4(), name="Ryan Gosling"),
        ]


class Query(GQL):
    def account_by_username(self, username: str) -> Account:  # (5)!
        # Usually we'd use a database to get this account. For this example, it is hardcoded.
        return Account(id=uuid4(), username=username)


router = build_router(query_models=[Query])

app = FastAPI()  # (3)!

app.include_router(router, prefix="/graphql")
