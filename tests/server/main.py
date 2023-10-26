import typing as T
import time
from fastapi import FastAPI, Response, Request
from fastgql.schema_builder import SchemaBuilder

from tests.server.services.users.gql import Query as UserQuery, Mutation as UserMutation

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


# QB.build_from_schema(schema, use_camel_case=CAMEL_CASE)
# Access.build_access_levels_from_schema(schema, use_camel_case=CAMEL_CASE)

router = SchemaBuilder.build_router(
    query_models=[UserQuery], mutation_models=[UserMutation], use_camel_case=True
)
app.include_router(router, prefix="/graphql")
