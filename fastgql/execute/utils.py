import typing as T
from collections import OrderedDict
from dataclasses import dataclass

from pydantic import create_model
import graphql

from fastgql.info import Info, ContextType
from fastgql.gql_models import GQL, GQLError

InfoType = T.TypeVar("InfoType", bound=Info)


@dataclass
class Result:
    data: T.Any | None
    errors: list[graphql.GraphQLError] | None
    extensions: list[T.Any] | None


def gql_errors_to_graphql_errors(
    gql_errors: list[GQLError],
) -> list[graphql.GraphQLError]:
    graphql_errors: list[graphql.GraphQLError] = []
    for e in gql_errors:
        graphql_errors.append(
            graphql.GraphQLError(
                message=e.message,
                nodes=e.node.original_node if e.node else None,
                path=e.path,
                original_error=e.original_error,
                extensions=e.extensions,
            )
        )
    return graphql_errors


class CacheDict(OrderedDict):
    """Dict with a limited length, ejecting LRUs as needed."""

    def __init__(self, *args, cache_len: int, **kwargs):
        assert cache_len > 0
        self.cache_len = cache_len

        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        super().move_to_end(key)

        while len(self) > self.cache_len:
            oldkey = next(iter(self))
            super().__delitem__(oldkey)

    def __getitem__(self, key):
        val = super().__getitem__(key)
        super().move_to_end(key)

        return val


def combine_models(name: str, *models: T.Type[GQL]) -> T.Type[GQL]:
    combined_model = create_model(name, __base__=GQL)

    seen_fields = set()
    excluded_methods = set(dir(GQL))

    for model in models:
        for field_name, field_value in model.model_fields.items():
            if field_name in seen_fields:
                raise ValueError(f"Conflicting field: {field_name}")
            setattr(combined_model, field_name, field_value)
            seen_fields.add(field_name)

        for method_name in dir(model):
            if (
                not method_name.startswith("_")
                and callable(getattr(model, method_name))
                and method_name not in excluded_methods
            ):
                method = getattr(model, method_name)
                if isinstance(model.__dict__.get(method_name), staticmethod):
                    method = staticmethod(method)
                elif isinstance(model.__dict__.get(method_name), classmethod):
                    method = classmethod(method)
                if method_name in dir(combined_model):
                    raise ValueError(f"Conflicting method: {method_name}")
                setattr(combined_model, method_name, method)

    combined_model.model_rebuild()
    return combined_model


def parse_value(variables: dict[str, T.Any] | None, v: T.Any) -> T.Any:
    if isinstance(v, dict):
        return {
            k: parse_value(variables=variables, v=inner_v) for k, inner_v in v.items()
        }
    if isinstance(v, list):
        return [parse_value(variables=variables, v=inner_v) for inner_v in v]
    if isinstance(v, graphql.VariableNode):
        return variables[v.name.value]
    return v


def build_is_not_nullable_map(
    schema: graphql.GraphQLSchema,
) -> dict[str, dict[str, bool]]:
    is_not_nullable_map: dict[str, dict[str, bool]] = {}
    for type_name, gql_type in schema.type_map.items():
        if isinstance(gql_type, graphql.GraphQLObjectType):
            is_not_nullable_map[type_name] = {}
            type_map = is_not_nullable_map[type_name]
            for field_name, field_val in gql_type.fields.items():
                field_val: graphql.GraphQLField
                type_map[field_name] = isinstance(
                    field_val.type, graphql.GraphQLNonNull
                )
    return is_not_nullable_map


def get_root_type(
    gql_field: graphql.GraphQLField | graphql.GraphQLObjectType,
) -> graphql.GraphQLObjectType | list[graphql.GraphQLObjectType]:
    if isinstance(gql_field, graphql.GraphQLObjectType):
        return gql_field
    t = gql_field.type
    while True:
        if isinstance(t, graphql.GraphQLUnionType):
            return [get_root_type(gql_field=tt) for tt in t.types]
        if isinstance(t, graphql.GraphQLObjectType):
            return t
        t = t.of_type


__all__ = [
    "InfoType",
    "ContextType",
    "get_root_type",
    "build_is_not_nullable_map",
    "parse_value",
    "combine_models",
    "Result",
    "gql_errors_to_graphql_errors",
    "CacheDict",
    "Info",
]
