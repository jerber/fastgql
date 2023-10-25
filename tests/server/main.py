import typing as T
import time
import graphql
from fastapi import FastAPI, BackgroundTasks, Response, Request
from dataclasses import dataclass
from starlette import status
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastgql.execute.utils import combine_models, Info, build_is_not_nullable_map
from fastgql.execute.executor import Executor
from fastgql.schema_builder import SchemaBuilder

from tests.server.services.users.gql import Query as UserQuery, Mutation as UserMutation

Query = combine_models("Query", UserQuery)
Mutation = combine_models("Mutation", UserMutation)

app = FastAPI()


# register_profiling_middleware(app)


@app.middleware("http")
async def add_error_handling_and_process_time_header(
    request: Request, call_next: T.Any
) -> Response:
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time-Ms"] = str(process_time * 1_000)
    return response


CAMEL_CASE = True
builder = SchemaBuilder(use_camel_case=CAMEL_CASE)
query = builder.convert_model_to_gql(
    model=Query, is_input=False, ignore_if_has_seen=False
)
mutation = builder.convert_model_to_gql(
    model=Mutation, is_input=False, ignore_if_has_seen=False
)
schema = graphql.GraphQLSchema(
    query=query,
    mutation=mutation,
)
is_not_nullable_map = build_is_not_nullable_map(schema)
# QB.build_from_schema(schema, use_camel_case=CAMEL_CASE)
# Access.build_access_levels_from_schema(schema, use_camel_case=CAMEL_CASE)
sdl = graphql.print_schema(schema)
# print(sdl)
import json

executor = Executor(
    schema_builder=builder,
    schema=schema,
    query_model=Query(),
    mutation_model=Mutation(),
)

from fastgql import get_graphiql_html


@app.get(
    "/graphql",
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


def get_user(request_data: GraphQLRequestData) -> dict:
    return {"id": "123"}


@app.post("/graphql")
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
            schema=schema,
            source=request_data.query,
            variable_values=request_data.variables,
            operation_name=request_data.operation_name,
        )
    else:
        res = await executor.execute(
            source=request_data.query,
            variable_values=request_data.variables,
            operation_name=request_data.operation_name,
            request=request,
            response=response,
            bt=background_tasks,
            info_cls=Info,
            use_camel_case=CAMEL_CASE,
            use_cache=True,
        )
    if res.errors:
        # TODO idk how do to these errors...
        # for error in res.errors:
        #     raise error
        serialized_errors = [serialize_graphql_error(error) for error in res.errors]
    else:
        serialized_errors = None
    start = time.time()
    json_r = JSONResponse(
        {
            "data": res.data,
            "errors": serialized_errors,
            "extensions": res.extensions,
        }
    )
    print(f"json response parsing took {(time.time() - start) * 1000:.2f} ms")
    return json_r


@app.post("/graphql")
async def handle_http_query_old(
    request: Request,
    # context=Depends(self.context_getter),
    # root_value=Depends(self.root_value_getter),
) -> Response:
    print("IN HERE!")
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return PlainTextResponse(
                "Unable to parse request body as JSON",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    # elif content_type.startswith("multipart/form-data"):
    #     multipart_data = await request.form()
    #     operations = json.loads(multipart_data.get("operations", {}))
    #     files_map = json.loads(multipart_data.get("map", {}))
    #     data = replace_placeholders_with_files(operations, files_map, multipart_data)
    else:
        return PlainTextResponse(
            "Unsupported Media Type",
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )

    """
    try:
        request_data = parse_request_data(data)
    except MissingQueryError:
        return PlainTextResponse(
            "No GraphQL query found in the request",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    result = await self.execute(
        request_data.query,
        variables=request_data.variables,
        context=context,
        operation_name=request_data.operation_name,
        root_value=root_value,
    )

    response_data = await self.process_result(request, result)

    return JSONResponse(response_data, status_code=status.HTTP_200_OK)
    """

    # debug(data)
    res = await graphql.graphql(schema, data["query"])
    # debug(res)
    return JSONResponse(
        res.data,
        status_code=status.HTTP_200_OK,
    )
