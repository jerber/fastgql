import typing as T
import dataclasses
from fastgql.gql_ast import models as M
from fastgql.context import BaseContext

ContextType = T.TypeVar("ContextType", bound=BaseContext)


@dataclasses.dataclass
class Info(T.Generic[ContextType]):
    """needed to make this a raw dataclass because context needs to be kept as a reference... pydantic copies dicts"""

    node: M.FieldNode | M.InlineFragmentNode
    parent_node: M.FieldNode | M.InlineFragmentNode | M.OperationNode
    path: tuple[str, ...]

    context: ContextType


__all__ = ["Info", "ContextType"]
