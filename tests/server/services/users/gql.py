import datetime
import typing as T
import uuid
from uuid import UUID
from pydantic import Field
from fastgql.gql_models import GQL, GQLInput
from fastgql import Depends, FieldNode

from fastgql.query_builders.sql.logic import (
    Link,
    Property,
    get_qb,
    QueryBuilder,
    Cardinality,
)
from devtools import debug


class User(GQL):
    sql_table_name: T.ClassVar[str] = '"User"'

    id: T.Annotated[UUID, Property(path_to_value="$current.id")] = Field(
        ..., description="ID for user."
    )
    name: T.Annotated[str, Property(path_to_value="$current.name")] = None
    first_name: T.Annotated[
        str, Property(path_to_value="split_part($current.name, ' ', 1)")
    ] = None
    slug: T.Annotated[str, Property(path_to_value="$current.slug")] = None

    def nickname(self) -> str:
        """
        builds nickname
        :return: str
        """
        return f"lil {self.name}"


def update_qbs_bookings(child_qb: QueryBuilder) -> None:
    child_qb.set_where("status_v2 = 'confirmed'")


def bookings_count_update_qb(
    qb: QueryBuilder,
    child_node: FieldNode,
    status: str,
    limit: int,
) -> None:
    qb.sel(
        alias=child_node.alias or child_node.name,
        path=f'(SELECT count(*) FROM "Booking" WHERE "Booking".artist_id = $current.id AND status_v2 = $status LIMIT {limit})',
        variables={"status": status},
    )
    debug(qb, status, limit)


class Artist(GQL):
    sql_table_name: T.ClassVar[str] = '"Artist"'

    id: T.Annotated[UUID, Property(path_to_value="$current.id")] = Field(
        ..., description="ID for artist."
    )
    name: T.Annotated[str, Property(path_to_value="$current.name")] = None
    slug: T.Annotated[str, Property(path_to_value="$current.slug")] = None

    def bookings(
        self
    ) -> T.Annotated[
        list["Booking"],
        Link(
            from_where="$current.artist_id = $parent.id",
            cardinality=Cardinality.MANY,
            update_qbs=update_qbs_bookings,
        ),
    ]:
        return []

    bookings_count: T.Annotated[
        int,
        Property(
            path_to_value='(SELECT count(*) FROM "Booking" WHERE "Booking".artist_id = $current.id)'
        ),
    ] = None

    # TODO, having non link or property, something else. It is a property that needs more flex for
    # updating the qb
    def bookings_count_filtered(
        self, status: str, limit: int
    ) -> T.Annotated[
        int, Property(update_qb=bookings_count_update_qb, path_to_value=None)
    ]:
        return 9


class Booking(GQL):
    sql_table_name: T.ClassVar[str] = '"Booking"'

    id: T.Annotated[UUID, Property(path_to_value="$current.id")] = None
    start_time: T.Annotated[
        datetime.datetime, Property(path_to_value="$current.start_time")
    ] = None


class UserInput(GQLInput):
    name: str = None


class Query(GQL):
    @staticmethod
    async def get_user() -> User:
        return User(
            id=uuid.uuid4(), name="Frank Stove", slug="frank", first_name="Frank"
        )

    @staticmethod
    async def get_users(
        limit: int, offset: int, qb: QueryBuilder = Depends(get_qb)
    ) -> list[User]:
        # use this to test sql query builder
        s, v = qb.set_limit(limit).set_offset(offset).build_root(format_sql=True)
        print(s, v)
        return []

    @staticmethod
    async def get_artist_by_slug(
        slug: str, qb: QueryBuilder = Depends(get_qb)
    ) -> Artist | None:
        s, v = qb.set_where("$current.slug = $slug", {"slug": slug}).build_root(
            format_sql=True
        )
        print(s, v)
        return None


class Mutation(GQL):
    @staticmethod
    async def create_user(input: UserInput) -> User:
        return User(id=uuid.uuid4(), name=input.name or "Paul")
