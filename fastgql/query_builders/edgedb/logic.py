import typing as T
import time
import inspect
import graphql
from pydantic import alias_generators

from fastgql.execute.utils import get_root_type
from .config import QueryBuilderConfig, Link, Property


def get_qb_config_from_gql_field(
    gql_field: graphql.GraphQLField, path_to_return_cls: tuple[str, ...] = None
) -> QueryBuilderConfig:
    root = get_root_type(gql_field)
    if path_to_return_cls:
        path = [*path_to_return_cls]
        while path:
            p = path.pop(0)
            root = get_root_type(root.fields[p])
    if isinstance(root, list):
        child_qb_config = {cm.name: cm._pydantic_model.qb_config for cm in root}
    else:
        child_qb_config = root._pydantic_model.qb_config
    return child_qb_config


def to_camel(s: str, use_camel_case: bool) -> str:
    if use_camel_case:
        return alias_generators.to_camel(s)
    return s


def build_from_schema(schema: graphql.GraphQLSchema, use_camel_case: bool) -> None:
    start = time.time()
    print("starting to build gql")
    gql_models = [
        m
        for m in schema.type_map.values()
        if isinstance(m, graphql.GraphQLObjectType) and hasattr(m, "_pydantic_model")
    ]
    for gql_model in gql_models:
        gql_model._pydantic_model.qb_config = QueryBuilderConfig(
            properties={}, links={}
        )
    for gql_model in gql_models:
        pydantic_model = gql_model._pydantic_model
        config: QueryBuilderConfig = pydantic_model.qb_config
        # first do fields
        for field_name, field_info in pydantic_model.model_fields.items():
            meta_list = field_info.metadata
            for meta in meta_list:
                if isinstance(meta, Property):
                    config.properties[field_name] = meta
                elif isinstance(meta, Link):
                    # but then need to populated nested
                    if not meta.return_cls_qb_config:
                        meta.return_cls_qb_config = get_qb_config_from_gql_field(
                            gql_model.fields[field_name]
                        )
                    config.links[field_name] = meta
        # now do functions
        for name, member in inspect.getmembers(pydantic_model):
            if inspect.isfunction(member):
                return_annotation = inspect.signature(member).return_annotation
                if isinstance(return_annotation, (T.Annotated, T._AnnotatedAlias)):
                    for meta in return_annotation.__metadata__:
                        if isinstance(meta, Link):
                            if not meta.return_cls_qb_config:
                                meta.return_cls_qb_config = (
                                    get_qb_config_from_gql_field(
                                        gql_model.fields[
                                            to_camel(
                                                name, use_camel_case=use_camel_case
                                            )
                                        ],
                                        path_to_return_cls=meta.path_to_return_cls,
                                    )
                                )
                            config.links[name] = meta

    # for gql_model in gql_models:
    #     if gql_model.name == "EventUserPublic":
    #         print(gql_model.name)
    #         debug(gql_model._pydantic_model.qb_config)
    print(
        f"[QB CONFIG BUILDING] building the qb configs took: {(time.time() - start) * 1000} ms"
    )
