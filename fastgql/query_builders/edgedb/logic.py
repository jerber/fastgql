import typing as T
import types
import time
import inspect
import graphql
from pydantic import alias_generators, BaseModel
from devtools import debug

from fastgql.execute.utils import get_root_type
from fastgql.info import Info
from .config import QueryBuilderConfig, Link, Property
from .query_builder import QueryBuilder


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


def root_type_s_from_annotation(
    a: T.Any,
) -> T.Type[BaseModel] | list[T.Type[BaseModel]]:
    if inspect.isclass(a):
        return a
    else:
        origin = T.get_origin(a)
        args = T.get_args(a)
        if origin is list or origin is types.UnionType or origin is T.Union:
            non_none_args = []
            for arg in args:
                if not (
                    arg is None
                    or (inspect.isclass(arg) and issubclass(arg, type(None)))
                ):
                    non_none_args.append(arg)
            if len(non_none_args) == 1:  # that means non was taken out?
                return root_type_s_from_annotation(non_none_args[0])
            else:
                return [root_type_s_from_annotation(arg) for arg in args]


async def get_qb(info: Info) -> QueryBuilder:
    annotation = info.node.annotation
    root_type_s = root_type_s_from_annotation(annotation)
    if type(root_type_s) is list:
        existing_config = None
        for root_type in root_type_s:
            qb_config: QueryBuilderConfig = getattr(root_type, "qb_config", None)
            if qb_config and not qb_config.is_empty():
                if existing_config:
                    debug(qb_config, existing_config)
                    raise Exception("You cannot have conflicting qb_configs.")
                existing_config = qb_config
        if not existing_config:
            raise Exception("There is no return model with a qb_config.")
        return await existing_config.from_info(info=info, node=info.node)
    else:
        return await root_type_s.qb_config.from_info(info=info, node=info.node)
