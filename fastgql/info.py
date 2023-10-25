import typing as T
import dataclasses
from fastapi import Request, Response, BackgroundTasks
from fastgql.gql_ast import models as M


@dataclasses.dataclass
class Info:
    """needed to make this a raw dataclass because context needs to be kept as a reference... pydantic copies dicts"""

    variables: dict[str, T.Any] | None

    node: M.FieldNode | M.InlineFragmentNode
    parent_node: M.FieldNode | M.InlineFragmentNode | M.OperationNode
    context: dict[str, T.Any]

    request: Request
    response: Response
    background_tasks: BackgroundTasks

    errors: list[Exception]

    path: tuple[str, ...]

    @property
    def alias(self) -> str:
        if isinstance(self.node, M.FieldNode):
            return self.node.alias or self.node.display_name
        raise Exception("Only FieldNodes have aliases.")
