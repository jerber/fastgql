import typing as T
from datetime import datetime
from graphql import GraphQLScalarType, ValueNode
from graphql.utilities import value_from_ast_untyped


def serialize_datetime(value: datetime) -> str:
    return value.isoformat()


def parse_datetime_value(value: T.Any) -> datetime:
    return datetime.fromisoformat(value)


def parse_datetime_literal(
    value_node: ValueNode, variables: T.Optional[T.Dict[str, T.Any]] = None
) -> datetime:
    ast_value = value_from_ast_untyped(value_node, variables)
    return parse_datetime_value(ast_value)


DateTimeScalar = GraphQLScalarType(
    name="DateTime",
    description="Datetime given as ISO",
    serialize=serialize_datetime,
    parse_value=parse_datetime_value,
    parse_literal=parse_datetime_literal,
)

UUIDScalar = GraphQLScalarType(name="UUID")
DateScalar = GraphQLScalarType(name="Date")
TimeScalar = GraphQLScalarType(name="Time")

__all__ = ["UUIDScalar", "DateScalar", "TimeScalar", "DateTimeScalar"]
