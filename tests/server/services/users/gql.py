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

    id: T.Annotated[UUID, Property(path="$current.id")] = Field(
        ..., description="ID for user."
    )
    name: T.Annotated[str, Property(path="$current.name")] = None
    first_name: T.Annotated[
        str, Property(path="split_part($current.name, ' ', 1)")
    ] = None
    slug: T.Annotated[str, Property(path="$current.slug")] = None

    def nickname(self) -> str:
        """
        builds nickname
        :return: str
        """
        return f"lil {self.name}"

    def artists(
        self
    ) -> T.Annotated[
        list["Artist"],
        Link(
            cardinality=Cardinality.MANY,
            from_='FROM "Artist.sellers" JOIN "Artist" $current ON "Artist.sellers".source = $current.id WHERE "Artist.sellers".target = $parent.id',
        ),
    ]:
        ...


def update_qbs_bookings(child_qb: QueryBuilder) -> None:
    child_qb.and_where("status_v2 = 'confirmed'")


def bookings_count_update_qb(
    qb: QueryBuilder,
    child_node: FieldNode,
    status: str,
    limit: int,
) -> None:
    qb.sel(
        name=child_node.alias or child_node.name,
        path=f'(SELECT count(*) FROM "Booking" WHERE "Booking".artist_id = $current.id AND status_v2 = $status LIMIT {limit})',
        variables={"status": status},
    )
    debug(qb, status, limit)


class Artist(GQL):
    sql_table_name: T.ClassVar[str] = '"Artist"'

    id: T.Annotated[UUID, Property(path="$current.id")] = Field(
        ..., description="ID for artist."
    )
    name: T.Annotated[str, Property(path="$current.name")] = None
    slug: T.Annotated[str, Property(path="$current.slug")] = None

    def bookings(
        self
    ) -> T.Annotated[
        list["Booking"],
        Link(
            from_='FROM "Booking" $current WHERE $current.artist_id = $parent.id',
            cardinality=Cardinality.MANY,
            update_qbs=update_qbs_bookings,
        ),
    ]:
        return []

    bookings_count: T.Annotated[
        int,
        Property(
            path='(SELECT count(*) FROM "Booking" WHERE "Booking".artist_id = $current.id)'
        ),
    ] = None

    # TODO, having non link or property, something else. It is a property that needs more flex for
    # updating the qb
    def bookings_count_filtered(
        self, status: str, limit: int
    ) -> T.Annotated[int, Property(update_qb=bookings_count_update_qb, path=None)]:
        return 9

    def sellers(
        self
    ) -> T.Annotated[
        list[User],
        Link(
            cardinality=Cardinality.MANY,
            from_='FROM "Artist.sellers" JOIN "User" $current ON "Artist.sellers".target = $current.id WHERE "Artist.sellers".source = $parent.id',
        ),
    ]:
        """
        # this is what you want:
        SELECT json_build_object('sellers',
                         (SELECT json_agg(Artist__User_json) AS Artist__User_json_agg
                          FROM (SELECT json_build_object('id', Artist__User.id, 'name', Artist__User.name) AS Artist__User_json

                                FROM "Artist.sellers"
                                         JOIN "User" Artist__User ON "Artist.sellers".target = Artist__User.id

                                WHERE "Artist.sellers".source = _Artist.id) AS Artist__Booking_json_sub)) AS _Artist_json
        FROM "Artist" _Artist
        WHERE _Artist.slug = 'penningtonstationband'
        :return:
        """
        ...


class Booking(GQL):
    sql_table_name: T.ClassVar[str] = '"Booking"'

    id: T.Annotated[UUID, Property(path="$current.id")] = None
    start_time: T.Annotated[
        datetime.datetime, Property(path="$current.start_time")
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
        s, v = qb.and_where("$current.slug = $slug", {"slug": slug}).build_root(
            format_sql=True
        )
        print(s, v)
        return None


class Mutation(GQL):
    @staticmethod
    async def create_user(input: UserInput) -> User:
        return User(id=uuid.uuid4(), name=input.name or "Paul")
