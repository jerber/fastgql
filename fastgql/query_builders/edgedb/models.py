import typing as T
from pydantic import BaseModel
from fastgql.query_builders.edgedb.config import QueryBuilderConfig


class QB(BaseModel):
    qb_config: T.ClassVar[QueryBuilderConfig]
