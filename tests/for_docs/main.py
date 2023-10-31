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

if __name__ == "__main__":
    import os
    import uvicorn

    os.environ["DOPPLER_ENV"] = "1"
    os.environ["HOST"] = "0.0.0.0"
    os.environ["PORT"] = "8001"
    os.environ["STAGE"] = "local"
    reload = bool(int(os.getenv("RELOAD", 1)))
    uvicorn.run(
        "tests.for_docs.main:app",
        host=os.environ["HOST"],
        port=int(os.environ["PORT"]),
        reload=reload,
        log_level="info",
    )
