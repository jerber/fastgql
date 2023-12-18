import typing as T
from uuid import UUID
import json
from datetime import datetime, date, time
from graphql import GraphQLScalarType, ValueNode
from graphql.utilities import value_from_ast_untyped
from pydantic_core import to_jsonable_python


def serialize_datetime(value: datetime) -> str:
    return value.isoformat()


def parse_datetime_value(value: T.Any) -> datetime:
    return datetime.fromisoformat(value)


def parse_datetime_literal(
    value_node: ValueNode, variables: T.Optional[T.Dict[str, T.Any]] = None
) -> datetime:
    ast_value = value_from_ast_untyped(value_node, variables)
    return parse_datetime_value(ast_value)


def serialize_date(value: date) -> str:
    return value.isoformat()


def parse_date_value(value: T.Any) -> date:
    return date.fromisoformat(value)


def parse_date_literal(
    value_node: ValueNode, variables: T.Optional[T.Dict[str, T.Any]] = None
) -> date:
    ast_value = value_from_ast_untyped(value_node, variables)
    return parse_date_value(ast_value)


def serialize_time(value: time) -> str:
    return value.isoformat()


def parse_time_value(value: T.Any) -> time:
    return time.fromisoformat(value)


def parse_time_literal(
    value_node: ValueNode, variables: T.Optional[T.Dict[str, T.Any]] = None
) -> time:
    ast_value = value_from_ast_untyped(value_node, variables)
    return parse_time_value(ast_value)


def serialize_uuid(value: UUID) -> str:
    return str(value)


def parse_uuid_value(value: T.Any) -> UUID:
    return UUID(value)


def parse_uuid_literal(
    value_node: ValueNode, variables: T.Optional[T.Dict[str, T.Any]] = None
) -> UUID:
    ast_value = value_from_ast_untyped(value_node, variables)
    return parse_uuid_value(ast_value)


def serialize_json(value: dict) -> str:
    return json.dumps(to_jsonable_python(value))


def parse_json_value(value: T.Any) -> dict:
    return json.loads(value)


def parse_json_literal(
    value_node: ValueNode, variables: T.Optional[T.Dict[str, T.Any]] = None
) -> dict:
    ast_value = value_from_ast_untyped(value_node, variables)
    return parse_json_value(ast_value)


DateTimeScalar = GraphQLScalarType(
    name="DateTime",
    description="Datetime given as ISO.",
    serialize=serialize_datetime,
    parse_value=parse_datetime_value,
    parse_literal=parse_datetime_literal,
)

UUIDScalar = GraphQLScalarType(
    name="UUID",
    description="UUID given as String.",
    serialize=serialize_uuid,
    parse_value=parse_uuid_value,
    parse_literal=parse_uuid_literal,
)
DateScalar = GraphQLScalarType(
    name="Date",
    description="Date given as ISO.",
    serialize=serialize_date,
    parse_value=parse_date_value,
    parse_literal=parse_date_literal,
)
TimeScalar = GraphQLScalarType(
    name="Time",
    description="Time given as ISO.",
    serialize=serialize_time,
    parse_value=parse_time_value,
    parse_literal=parse_time_literal,
)
JSONScalar = GraphQLScalarType(
    name="JSON",
    description="JSON.",
    serialize=serialize_json,
    parse_value=parse_json_value,
    parse_literal=parse_json_literal,
)

__all__ = ["UUIDScalar", "DateScalar", "TimeScalar", "DateTimeScalar", "JSONScalar"]
