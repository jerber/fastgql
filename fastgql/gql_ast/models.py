import typing as T
from dataclasses import dataclass
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


@dataclass
class Node:
    original_node: graphql.Node
    children: list[T.Union["FieldNode", "InlineFragmentNode"]] | None

    overwrite_return_value: bool
    overwrite_return_value_to: T.Any | None

    def set_return_value_to(self, val: T.Any) -> None:
        self.overwrite_return_value = True
        self.overwrite_return_value_to = val

    def unset_return_value(self) -> None:
        self.overwrite_return_value = False
        self.overwrite_return_value_to = None


@dataclass
class FieldNode(Node):
    name: str
    alias: str | None
    display_name: str
    arguments: list[Argument]
    annotation: T.Any


@dataclass
class FieldNodeField(FieldNode):
    field: FieldInfo


@dataclass
class FieldNodeMethod(FieldNode):
    method: T.Callable


@dataclass
class FieldNodeModel(FieldNode):
    models: list[T.Type[BaseModel]]


@dataclass
class InlineFragmentNode(Node):
    type_condition: str
    annotation: T.Any


@dataclass
class OperationNode(Node):
    name: str | None
    type: OperationType


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
