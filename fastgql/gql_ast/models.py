import typing as T
import uuid
from dataclasses import dataclass, field
from enum import Enum
import graphql
from pydantic import BaseModel
from pydantic.fields import FieldInfo


class OperationType(str, Enum):
    query = "query"
    mutation = "mutation"


@dataclass
class Argument:
    name: str
    display_name: str
    value: T.Any | None


@dataclass(frozen=True)
class Node:
    id: uuid.UUID
    original_node: graphql.Node
    children: list[T.Union["FieldNode", "InlineFragmentNode"]] | None

    def __hash__(self):
        return hash(self.id)


@dataclass(frozen=True)
class FieldNode(Node):
    name: str
    alias: str | None
    display_name: str
    arguments: list[Argument]
    annotation: T.Any

    def __hash__(self):
        return hash(self.id)


@dataclass(frozen=True)
class FieldNodeField(FieldNode):
    field: FieldInfo

    def __hash__(self):
        return hash(self.id)


@dataclass(frozen=True)
class FieldNodeMethod(FieldNode):
    method: T.Callable

    def __hash__(self):
        return hash(self.id)


@dataclass(frozen=True)
class FieldNodeModel(FieldNode):
    models: list[T.Type[BaseModel]]

    def __hash__(self):
        return hash(self.id)


@dataclass(frozen=True)
class InlineFragmentNode(Node):
    type_condition: str
    annotation: T.Any

    def __hash__(self):
        return hash(self.id)


@dataclass(frozen=True)
class OperationNode(Node):
    name: str | None
    type: OperationType

    def __hash__(self):
        return hash(self.id)


__all__ = [
    "OperationType",
    "Argument",
    "Node",
    "FieldNode",
    "FieldNodeField",
    "FieldNodeModel",
    "FieldNodeMethod",
    "InlineFragmentNode",
    "OperationNode",
]
