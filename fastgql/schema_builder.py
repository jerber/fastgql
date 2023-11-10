import typing as T
from dataclasses import dataclass
import time
import types
import datetime
import enum
import uuid
import json
import inspect
import functools
import graphql
import pydantic
import pydantic_core
from pydantic.fields import FieldInfo
from pydantic.alias_generators import to_camel
from fastapi import APIRouter, Response, Request, status, BackgroundTasks
from fastapi.responses import HTMLResponse, PlainTextResponse, ORJSONResponse

from fastgql.utils import get_graphiql_html
from fastgql.scalars import DateTimeScalar, UUIDScalar, DateScalar, TimeScalar
from fastgql.gql_models import GQL, GQLInput, GQLInterface
from fastgql.info import Info
from fastgql.depends import Depends
from fastgql.execute.utils import combine_models
from fastgql.execute.executor import Executor, InfoType, ContextType
from fastgql.query_builders.edgedb import logic as qb_logic
from fastgql.context import BaseContext

BASEMODEL_DIR: list[str] = dir(pydantic.BaseModel)
GQL_DIR: list[str] = [*dir(GQL), *dir(GQLInput), *dir(GQLInterface)]
DIRS_TO_IGNORE: set[str] = {*BASEMODEL_DIR, *GQL_DIR}

ModelType = T.TypeVar("ModelType", bound=T.Type[GQL])

mapping: dict[type, T.Any] = {
    str: graphql.GraphQLString,
    # enum.Enum: GraphQLEnumType,
    int: graphql.GraphQLInt,
    float: graphql.GraphQLFloat,
    bool: graphql.GraphQLBoolean,
    datetime.datetime: DateTimeScalar,
    uuid.UUID: UUIDScalar,
    datetime.date: DateScalar,
    datetime.time: TimeScalar,
}

GT = T.TypeVar("GT", bound=graphql.GraphQLType)

enum_cache: dict[T.Type[enum.Enum], graphql.GraphQLEnumType] = {}

union_cache: dict[str, graphql.GraphQLUnionType] = {}


@dataclass
class GraphQLRequestData:
    # query is optional here as it can be added by an extensions
    # (for example an extension for persisted queries)
    query: str | None
    variables: dict[str, T.Any] | None
    operation_name: str | None


class MissingQueryError(Exception):
    def __init__(self):
        message = 'Request data is missing a "query" value'

        super().__init__(message)


def parse_request_data(data: T.Mapping[str, T.Any]) -> GraphQLRequestData:
    query = data.get("query")
    if not query:
        raise MissingQueryError()
    return GraphQLRequestData(
        query=query,
        variables=data.get("variables"),
        operation_name=data.get("operationName"),
    )


def serialize_graphql_error(error: graphql.GraphQLError) -> dict:
    return {
        "message": str(error.message),
        "locations": [
            location._asdict() for location in error.locations or []
        ],  # Assuming location is a named tuple
        "path": error.path,
        "extensions": error.extensions,
    }


def context_from_info(info_cls: T.Type[InfoType]) -> T.Type[ContextType] | None:
    # Access the original bases
    orig_bases = info_cls.__orig_bases__

    # Check if there's any base
    if orig_bases:
        base = orig_bases[0]

        # Check if the base is parameterized
        if hasattr(base, "__args__") and base.__args__:
            context_typevar = base.__args__[0]

            # Return the bound of the type variable
            if hasattr(context_typevar, "__bound__"):
                return context_typevar.__bound__

            if issubclass(context_typevar, BaseContext):
                return context_typevar

    return None


class SchemaBuilder:
    def __init__(
        self,
        *,
        query_models: list[T.Type[GQL]],
        mutation_models: list[T.Type[GQL]] | None = None,
        use_camel_case: bool = True,
        info_cls: T.Type[InfoType] | None = None,
    ):
        self.use_camel_case = use_camel_case
        self.info_cls = info_cls or Info
        self.context_cls = context_from_info(self.info_cls) or BaseContext

        query_model = combine_models("Query", *query_models)
        query = self.convert_model_to_gql(
            model=query_model,
            is_input=False,
            ignore_if_has_seen=False,
        )
        if mutation_models:
            mutation_model = combine_models("Mutation", *mutation_models)
            mutation = self.convert_model_to_gql(
                model=mutation_model,
                is_input=False,
                ignore_if_has_seen=False,
            )
        else:
            mutation_model = None
            mutation = None
        self.schema = graphql.GraphQLSchema(query=query, mutation=mutation)

        # now build QBs if QBs are found
        qb_logic.build_from_schema(
            schema=self.schema, use_camel_case=self.use_camel_case
        )

        self.executor = Executor(
            use_camel_case=self.use_camel_case,
            schema=self.schema,
            query_model=query_model(),
            mutation_model=mutation_model() if mutation_model else None,
        )

    @classmethod
    def build_router(
        cls,
        *,
        use_camel_case: bool = True,
        query_models: list[T.Type[GQL]],
        mutation_models: list[T.Type[GQL]] | None = None,
        allow_graphiql: bool = True,
        info_cls: T.Type[InfoType] | None = None,
    ):
        schema_builder = SchemaBuilder(
            use_camel_case=use_camel_case,
            query_models=query_models,
            mutation_models=mutation_models,
            info_cls=info_cls,
        )
        return schema_builder._build_router(allow_graphiql=allow_graphiql)

    def snake_to_camel(self, s: str) -> str:
        if self.use_camel_case:
            return to_camel(s)
        return s

    @functools.cache
    def gql_type_from_annotation(
        self, a: T.Type[T.Any], nullable: bool, is_input: bool
    ) -> (
        graphql.GraphQLType
        | graphql.GraphQLObjectType
        | graphql.GraphQLInterfaceType
        | graphql.GraphQLInputType
        | graphql.GraphQLInputObjectType
    ):
        if a in mapping:
            type_ = mapping[a]
        elif isinstance(a, type):
            if issubclass(a, enum.Enum):
                if a in enum_cache:
                    type_ = enum_cache[a]
                else:
                    type_ = graphql.GraphQLEnumType(name=a.__name__, values=a)
                    enum_cache[a] = type_
            elif issubclass(a, GQL) and not issubclass(a, Info):
                type_ = self.convert_model_to_gql(
                    a, is_input=is_input, ignore_if_has_seen=True
                )
            else:
                raise Exception(f"invalid sub {a=}")
        else:
            origin = T.get_origin(a)
            args = T.get_args(a)
            if origin in {set, tuple}:
                raise Exception("Cannot return a set or tuple. Must return a list.")
            if origin is list:
                type_ = graphql.GraphQLList(
                    type_=self.gql_type_from_annotation(
                        args[0], nullable=False, is_input=is_input
                    )
                )
            elif origin is types.UnionType or origin is T.Union:
                non_none_args = [arg for arg in args if not issubclass(arg, type(None))]
                has_none = len(non_none_args) != len(args)
                if len(non_none_args) == 1:  # that means non was taken out?
                    type_ = self.gql_type_from_annotation(
                        non_none_args[0], nullable=has_none, is_input=is_input
                    )
                else:
                    types_ = [
                        self.gql_type_from_annotation(
                            arg, nullable=has_none, is_input=is_input
                        )
                        for arg in non_none_args
                    ]
                    # unions cannot have non-nullable types within them but the union can be non-nullable
                    nullable_types: list[
                        graphql.GraphQLObjectType,
                        graphql.GraphQLInputObjectType,
                        graphql.GraphQLInterfaceType,
                    ] = []
                    for t in types_:
                        if isinstance(t, graphql.GraphQLNonNull):
                            t = t.of_type
                        nullable_types.append(t)
                        if not isinstance(
                            t,
                            (
                                graphql.GraphQLObjectType,
                                graphql.GraphQLInputObjectType,
                                graphql.GraphQLInterfaceType,
                            ),
                        ):
                            raise Exception(
                                f"You cannot have a union between non object types: {[t for t in types_]}"
                            )
                    key = "__".join([arg.__name__ for arg in non_none_args])
                    if key in union_cache:
                        type_ = union_cache[key]
                    else:
                        type_ = graphql.GraphQLUnionType(types=nullable_types, name=key)
                        union_cache[key] = type_
                if has_none:
                    nullable = True
            elif origin is None:
                raise Exception("Cannot return None for a graphql type.")
            else:
                raise Exception(f"Invalid here {a=}")
        if not nullable:
            type_ = graphql.GraphQLNonNull(type_)
        type_._anno = a
        return type_

    @functools.cache
    def field_info_to_gql_field(
        self, field_info: FieldInfo, is_input: bool
    ) -> graphql.GraphQLField | graphql.GraphQLInputField:
        a = field_info.annotation
        type_ = self.gql_type_from_annotation(a, nullable=False, is_input=is_input)
        type_._field_info = field_info
        if not is_input:
            field = graphql.GraphQLField(
                type_=type_, description=field_info.description
            )
        else:
            field = graphql.GraphQLInputField(
                type_=type_,
                description=field_info.description,
                default_value=field_info.default
                if field_info.default is not pydantic_core.PydanticUndefined
                else graphql.Undefined,
            )
        return field

    @staticmethod
    def is_annotation_nullable(annotation: T.Type[T.Any]) -> bool:
        """from gpt4"""
        origin = T.get_origin(annotation)
        if origin is T.Union:
            _args = T.get_args(annotation)
            if len(_args) == 2 and any(arg is type(None) for arg in _args):
                return True
        return False

    def args_from_function(self, func: T.Callable) -> graphql.GraphQLArgumentMap:
        args: graphql.GraphQLArgumentMap = {}
        # now for the params
        params = inspect.signature(func).parameters
        for og_param_name, param in params.items():
            if param.annotation is inspect.Signature.empty:
                continue
            try:
                if issubclass(param.annotation, graphql.GraphQLResolveInfo):
                    continue
                if issubclass(param.annotation, Info):
                    continue
                if issubclass(param.annotation, Request):
                    continue
                if issubclass(param.annotation, Response):
                    continue
                if issubclass(param.annotation, BackgroundTasks):
                    continue
                if isinstance(param.default, Depends):
                    # get the args from the depends!
                    args.update(self.args_from_function(param.default.dependency))
                    continue
            except TypeError:
                pass
            nullable = self.is_annotation_nullable(annotation=param.annotation)
            param_type_ = self.gql_type_from_annotation(
                param.annotation, nullable=nullable, is_input=True
            )
            if param.default is not inspect.Parameter.empty:
                default_value = param.default
            else:
                default_value = graphql.Undefined
            param_name = self.snake_to_camel(og_param_name)
            args[param_name] = graphql.GraphQLArgument(
                type_=param_type_, default_value=default_value
            )
        return args

    @staticmethod
    def get_actual_return_type(func: T.Callable, model_type: T.Type[GQL]) -> T.Type:
        # Get the type hints for the function
        type_hints = T.get_type_hints(func)
        # Extract the return type hint
        return_hint = type_hints.get("return")
        # If the return hint is a string (indicating a forward reference)
        if isinstance(return_hint, str):
            # Get the module where the model type is defined
            module = model_type.__module__
            # Evaluate the string within that module's namespace to get the actual type
            return_hint = eval(return_hint, globals().get(module).__dict__)

        return return_hint

    def build_gql_fields_from_model_methods(
        self,
        model: ModelType,
    ) -> dict[str, graphql.GraphQLField | graphql.GraphQLInputField]:
        gql_fields: dict[str, graphql.GraphQLField | graphql.GraphQLInputField] = {}
        attrs = [a for a in set(dir(model)) - DIRS_TO_IGNORE if not a.startswith("_")]
        for attr in attrs:
            func = getattr(model, attr)
            if not callable(func):
                # inbuilt attrs
                continue
            # return_type = inspect.signature(func).return_annotation
            # wow, get_actual_return_type really works. Should replace the old inspect.signature everywhere with it...
            return_type = self.get_actual_return_type(func=func, model_type=model)
            # if this does not return anything, ignore
            if return_type is inspect.Signature.empty:
                continue
            nullable = self.is_annotation_nullable(annotation=return_type)
            _return_type = self.gql_type_from_annotation(
                return_type, nullable=nullable, is_input=False
            )
            args = self.args_from_function(func)
            camel_attr = self.snake_to_camel(attr)
            field = graphql.GraphQLField(
                type_=_return_type,
                args=args,
                description=func.__doc__,
                # resolve=wrap_pydantic_resolver(func),
                resolve=func,
            )
            # field._method = func
            gql_fields[camel_attr] = field

        return gql_fields

    def build_gql_fields_from_model_fields(
        self, model: ModelType, is_input: bool
    ) -> dict[str, graphql.GraphQLField | graphql.GraphQLInputField]:
        gql_fields: dict[str, graphql.GraphQLField | graphql.GraphQLInputField] = {}
        for field_name, field_info in model.model_fields.items():
            gql_field = self.field_info_to_gql_field(
                field_info=field_info, is_input=is_input
            )
            if resolver := (getattr(field_info, "json_schema_extra") or {}).get(
                "resolver"
            ):
                gql_field.args = self.args_from_function(resolver)
            camel_attr = self.snake_to_camel(field_name)
            gql_fields[camel_attr] = gql_field
        return gql_fields

    def build_gql_fields_from_model(
        self, model: ModelType, is_input: bool
    ) -> dict[str, graphql.GraphQLField | graphql.GraphQLInputField]:
        gql_fields = self.build_gql_fields_from_model_fields(
            model=model, is_input=is_input
        )
        # maybe should error if it is not ("can't have funcs on inputs"). For now, ignore
        if not is_input:
            gql_fields.update(self.build_gql_fields_from_model_methods(model))

        return gql_fields

    MODEL_TO_GQL_CACHE: dict[
        str,
        dict[
            ModelType,
            T.Union[
                graphql.GraphQLObjectType,
                graphql.GraphQLInputObjectType,
                graphql.GraphQLInterfaceType,
            ],
        ],
    ] = {"inputs": dict(), "outputs": dict()}
    HAS_SEEN_MODEL: dict[str, set[ModelType]] = {"inputs": set(), "outputs": set()}

    def get_interfaces(self, model: T.Type[GQL]) -> list[graphql.GraphQLInterfaceType]:
        # now get inheritance
        interfaces: list[graphql.GraphQLInterfaceType] = []
        for sub_model in model.__mro__[1:]:
            if sub_model == GQLInterface:
                break
            if sub_model == GQL:
                break
            if issubclass(sub_model, GQLInterface):
                interfaces.append(
                    self.convert_model_to_gql(
                        model=sub_model, is_input=False, ignore_if_has_seen=False
                    )
                )
        return interfaces

    @functools.cache
    def convert_model_to_gql(
        self, model: ModelType, is_input: bool, ignore_if_has_seen: bool
    ) -> (
        graphql.GraphQLObjectType
        | graphql.GraphQLInputObjectType
        | graphql.GraphQLInterfaceType
    ):
        key = "inputs" if is_input else "outputs"
        cache = self.MODEL_TO_GQL_CACHE[key]
        has_seen = self.HAS_SEEN_MODEL[key]

        has_seen_model = model in has_seen
        has_seen.add(model)
        if ignore_if_has_seen and has_seen_model:
            gql_fields = {}
        else:
            gql_fields = self.build_gql_fields_from_model(
                model=model, is_input=is_input
            )
        if gql_fields and model in cache:
            o = cache[model]
            o._fields = lambda: gql_fields
        else:
            if is_input:
                if not issubclass(model, GQLInput):
                    raise Exception(
                        f"Model {model.__name__} must inherit from GQLInput."
                    )
                o = graphql.GraphQLInputObjectType(
                    name=model.gql_input_type_name(),
                    fields=lambda: gql_fields,
                    description=model.gql_description(),
                )
                o._pydantic_model = model
            else:
                if not issubclass(model, GQL):
                    raise Exception(f"Model {model.__name__} must inherit from GQL.")
                # if directly an interface...
                if model.__mro__[1] == GQLInterface:
                    o = graphql.GraphQLInterfaceType(
                        name=model.gql_type_name(),
                        fields=lambda: gql_fields,
                        interfaces=self.get_interfaces(model=model),
                    )
                else:
                    o = graphql.GraphQLObjectType(
                        name=model.gql_type_name(),
                        fields=lambda: gql_fields,
                        description=model.gql_description(),
                        interfaces=self.get_interfaces(model=model),
                    )
                o._pydantic_model = model
            cache[model] = o
        return o

    def _build_router(self, allow_graphiql: bool) -> APIRouter:
        router = APIRouter()

        if allow_graphiql:

            @router.get(
                "",
                responses={
                    200: {
                        "description": "The GraphiQL integrated development environment.",
                    },
                    404: {
                        "description": "Not found if GraphiQL is not enabled.",
                    },
                },
            )
            async def get_graphiql() -> HTMLResponse:
                return HTMLResponse(get_graphiql_html())

        @router.post("")
        async def handle_gql(
            request: Request, response: Response, background_tasks: BackgroundTasks
        ) -> Response:
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    data = await request.json()
                except json.JSONDecodeError:
                    return PlainTextResponse(
                        "Unable to parse request body as JSON",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return PlainTextResponse(
                    "Unsupported Media Type",
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                )

            try:
                request_data = parse_request_data(data)
            except MissingQueryError:
                return PlainTextResponse(
                    "No GraphQL query found in the request",
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            if request_data.operation_name == "IntrospectionQuery":
                res = await graphql.graphql(
                    schema=self.schema,
                    source=request_data.query,
                    variable_values=request_data.variables,
                    operation_name=request_data.operation_name,
                )
            else:
                res = await self.executor.execute(
                    source=request_data.query,
                    variable_values=request_data.variables,
                    operation_name=request_data.operation_name,
                    request=request,
                    response=response,
                    bt=background_tasks,
                    info_cls=self.info_cls,
                    context_cls=self.context_cls,
                    use_cache=True,
                )
            if res.errors:
                serialized_errors = [
                    serialize_graphql_error(error) for error in res.errors
                ]
            else:
                serialized_errors = None
            start = time.time()
            json_r = ORJSONResponse(
                {
                    "data": res.data,
                    "errors": serialized_errors,
                    "extensions": res.extensions,
                }
            )
            print(f"json response parsing took {(time.time() - start) * 1000:.2f} ms")
            return json_r

        return router
