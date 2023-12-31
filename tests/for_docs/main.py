from fastapi import FastAPI
from fastgql import GQL, build_router


class User(GQL):
    name: str
    age: int


class Query(GQL):
    @staticmethod
    def user() -> User:
        return User(name="Jeremy", age=27)


router = build_router(query_models=[Query])

app = FastAPI()

app.include_router(router, prefix="/graphql")
