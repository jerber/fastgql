import uuid
from uuid import UUID
from pydantic import Field
from fastgql.gql_models import GQL
from fastgql import Info
from devtools import debug


class User(GQL):
    id: UUID = Field(..., description='Id for user.')
    name: str

    def nickname(self) -> str:
        """
        builds nickname
        :return: str
        """
        return f"lil {self.name}"


class Query(GQL):
    @staticmethod
    async def get_user(info: Info) -> User:
        debug(info.context)
        return User(id=uuid.uuid4(), name="Frank Stove")


class Mutation(GQL):
    @staticmethod
    async def create_user() -> User:
        return User(id=uuid.uuid4(), name="Freddie Wilson")
