import typing as T
from pydantic import BaseModel, ValidationInfo, model_validator
from pydantic.alias_generators import to_snake
from fastgql.gql_ast.models import Node


class GQLConfigDict(T.TypedDict, total=False):
    """A TypedDict for configuring FastGQL behaviour."""

    type_name: str
    input_type_name: str
    description: str


class GQL(BaseModel):
    gql_config: T.ClassVar[GQLConfigDict] = {}

    @classmethod
    def gql_type_name(cls) -> str:
        return cls.gql_config.get("type_name", cls.__name__)

    @classmethod
    def gql_description(cls) -> str | None:
        return cls.gql_config.get("description")


class GQLInterface(GQL):
    pass


class GQLInput(GQL):
    @classmethod
    def gql_input_type_name(cls) -> str:
        return cls.gql_config.get("input_type_name", cls.__name__)

    @model_validator(mode="before")
    @classmethod
    def _to_snake_case(cls, data: T.Any, info: ValidationInfo) -> T.Any:
        if context := info.context:
            if context.get("_use_camel_case", False):
                fields = cls.model_fields
                d: dict[str, T.Any] = {}
                for k, v in data.items():
                    d[k] = v
                    if k in fields:
                        d[k] = v
                    else:
                        d[to_snake(k)] = v
                return d
        return data


class GQLError(Exception):
    def __init__(
        self,
        message: str,
        *,
        node: Node | list[Node] | None = None,
        path: tuple[str, ...] | None = None,
        original_error: Exception | None = None,
        extensions: dict[str, T.Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.node = node
        self.path = path
        self.original_error = original_error
        self.extensions = extensions


__all__ = ["GQL", "GQLInput", "GQLConfigDict", "GQLError", "GQLInterface"]
