from .gql_models import GQL, GQLInput, GQLError, GQLConfigDict
from .schema_builder import SchemaBuilder

build_router = SchemaBuilder.build_router

__all__ = [
    "SchemaBuilder",
    "build_router",
    "GQL",
    "GQLInput",
    "GQLError",
    "GQLConfigDict",
]
