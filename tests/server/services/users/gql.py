import typing as T
import uuid
from uuid import UUID
from pydantic import Field
from fastgql.gql_models import GQL, GQLInput
from fastgql import Info
from devtools import debug

from fastgql.query_builders.sql.logic import Link, Property, get_qb, QueryBuilderConfig
from fastgql.query_builders.sql.config import Cardinality

class User(GQL):
    id: UUID = Field(..., description="Id for user.")
    name: T.Annotated[str, Property(path_to_value='$current.name')] = None

    def nickname(self) -> str:
        """
        builds nickname
        :return: str
        """
        return f"lil {self.name}"


class UserInput(GQLInput):
    name: str = None


class Query(GQL):
    @staticmethod
    async def get_user(info: Info) -> User:

        User.qb_config_sql: QueryBuilderConfig
        qb = await User.qb_config_sql.from_info(info=info, node=info.node, cardinality=Cardinality.ONE)
        debug(qb)

        s, v = qb.build_root(format_sql=True)
        print(s)

        return User(id=uuid.uuid4(), name="Frank Stove")


class Mutation(GQL):
    @staticmethod
    async def create_user(input: UserInput) -> User:
        return User(id=uuid.uuid4(), name=input.name or "Paul")
