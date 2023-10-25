import uuid
from uuid import UUID
from fastgql.gql_models import GQL


class User(GQL):
    id: UUID
    name: str


class Query(GQL):
    @staticmethod
    async def get_user() -> User:
        return User(id=uuid.uuid4(), name="Frank Stove")


class Mutation(GQL):
    @staticmethod
    async def create_user() -> User:
        return User(id=uuid.uuid4(), name="Freddie Wilson")
