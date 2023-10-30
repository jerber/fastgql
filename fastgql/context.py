import typing as T
from fastapi import Request, Response, BackgroundTasks
from fastgql import GQLError


class BaseContext:
    def __init__(
        self,
        request: Request,
        response: Response,
        background_tasks: BackgroundTasks,
        errors: list[GQLError],
        variables: dict[str, T.Any],
    ):
        self.request = request
        self.response = response
        self.background_tasks = background_tasks
        self.errors = errors
        self.variables = variables
