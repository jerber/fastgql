from fastapi import FastAPI
from fastgql import GQL, build_router


class Actor(GQL):
    name: str


class Movie(GQL):
    title: str
    release_year: int
    actors: list[Actor]


class Query(GQL):
    def get_movies(self) -> list[Movie]:
        return [
            Movie(
                title="Barbie",
                release_year=2023,
                actors=[Actor(name="Margot Robbie")],
            )
        ]


router = build_router(query_models=[Query])

app = FastAPI()

app.include_router(router, prefix="/graphql")
