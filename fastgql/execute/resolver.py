import typing as T
import traceback
import asyncio
import inspect

from fastapi import Request, Response, BackgroundTasks
from pydantic import TypeAdapter

from fastgql.gql_ast import models as M
from fastgql.gql_models import GQL, GQLError
from fastgql.depends import Depends
from fastgql.execute.utils import InfoType, parse_value, Info, ContextType
from fastgql.utils import node_from_path


class Resolver:
    def __init__(
        self,
        *,
        use_camel_case: bool,
        info_cls: T.Type[InfoType],
        context_cls: T.Type[ContextType],
        is_not_nullable_map: dict[str, dict[str, bool]],
        variables: dict[str, T.Any] | None,
        request: Request,
        response: Response,
        bt: BackgroundTasks,
    ):
        self.use_camel_case = use_camel_case
        self.info_cls = info_cls
        self.is_not_nullable_map = is_not_nullable_map
        self.variables = variables

        self.request = request
        self.response = response
        self.bt = bt

        self.errors: list[GQLError] = []

        self.context: ContextType = context_cls(
            request=self.request,
            response=self.response,
            background_tasks=self.bt,
            errors=self.errors,
            variables=self.variables,
        )

    async def inject_dependencies(
        self, func: T.Callable[..., T.Any], kwargs: dict[str, T.Any], info: InfoType
    ) -> T.Any:
        # if you need to build kwargs, do it. Then execute
        new_kwargs = await self.build_kwargs(func=func, kwargs=kwargs, info=info)
        res = func(**new_kwargs)
        if inspect.isawaitable(res):
            res = await res
        return res

    async def build_kwargs(
        self, func: T.Callable[..., T.Any], kwargs: dict[str, T.Any], info: InfoType
    ) -> dict[str, T.Any]:
        new_kwargs: dict[str, T.Any] = {}
        sig = inspect.signature(func)
        for name, param in sig.parameters.items():
            if name in kwargs:
                val = kwargs[name]
                if val:
                    val = TypeAdapter(param.annotation).validate_python(
                        val,
                        context={
                            "_use_camel_case": self.use_camel_case,
                        },
                    )
                new_kwargs[name] = val
            else:
                if isinstance(param.default, Depends):
                    new_kwargs[name] = await self.inject_dependencies(
                        func=param.default.dependency, kwargs=kwargs, info=info
                    )
                elif inspect.isclass(param.annotation):
                    if issubclass(param.annotation, Info):
                        new_kwargs[name] = info
                    elif issubclass(param.annotation, Request):
                        new_kwargs[name] = self.request
                    elif issubclass(param.annotation, Response):
                        new_kwargs[name] = self.response
                    elif issubclass(param.annotation, BackgroundTasks):
                        new_kwargs[name] = self.bt
                # just continue, the value is not given and that is okay
        return new_kwargs

    def get_info_key(self, func: T.Callable[..., T.Any]) -> str | None:
        sig = inspect.signature(func)
        for name, param in sig.parameters.items():
            if param.annotation == self.info_cls:
                return name

    async def inject_dependencies_and_execute(
        self,
        node: M.FieldNode,
        parent: M.Node,
        method: T.Callable | T.Awaitable,
        kwargs: dict[str, T.Any],
        new_path: tuple[str, ...],
    ) -> dict[str, T.Any] | list[dict[str, T.Any]] | T.Any | None:
        # TODO if inefficient, lazily create info! Or maybe even cache it... or come up with a better way
        info = self.info_cls(
            node=node,
            parent_node=parent,
            path=new_path,
            context=self.context,
        )
        new_kwargs = await self.build_kwargs(func=method, kwargs=kwargs, info=info)
        child_model_s = method(**new_kwargs)
        if inspect.isawaitable(child_model_s):
            child_model_s = await child_model_s
        if child_model_s:
            if node.children:
                return await self.resolve_node_s(
                    node=node, model_s=child_model_s, path=new_path
                )
            else:
                return child_model_s
        return child_model_s

    async def resolve_node_s(
        self,
        node: M.FieldNode | M.OperationNode,
        model_s: list[GQL] | GQL,
        path: tuple[str, ...],
    ) -> dict[str, T.Any] | None | list[dict[str, T.Any] | None]:
        if isinstance(model_s, list):
            return list(
                await asyncio.gather(
                    *[
                        self.resolve_node(node=node, model=model, path=path)
                        for model in model_s
                    ]
                )
            )
        return await self.resolve_node(node=node, model=model_s, path=path)

    async def resolve_node(
        self,
        node: M.FieldNode | M.OperationNode,
        model: GQL,
        path: tuple[str, ...],
    ) -> dict[str, T.Any] | None:
        if model is None:
            return None
        if not isinstance(model, GQL):
            raise Exception(
                f"Model {model.__class__.__name__} must be an instance of GQL."
            )
        # return final dict, or array of dicts, for the node
        final_d: dict[str, T.Any] = {}
        fields_to_include: dict[str, str] = {}
        name_to_return_to_display_name: dict[str, str] = {}
        children_q = [*node.children]
        proms_map: dict[str, T.Awaitable] = {}
        while len(children_q) > 0:
            child = children_q.pop(0)
            if isinstance(child, M.InlineFragmentNode):
                if child.type_condition == model.gql_type_name():
                    children_q[:0] = child.children
                continue
            name_to_return = child.alias or child.display_name
            name_to_return_to_display_name[name_to_return] = child.display_name
            new_path = (*path, name_to_return)
            if child.name == "__typename":
                final_d[name_to_return] = model.gql_type_name()
            else:
                if child.name not in model.model_fields:
                    # this must be a function
                    kwargs = {
                        arg.name: parse_value(variables=self.variables, v=arg.value)
                        for arg in child.arguments
                    }
                    proms_map[name_to_return] = self.inject_dependencies_and_execute(
                        method=getattr(model, child.name),
                        node=child,
                        parent=node,
                        kwargs=kwargs,
                        new_path=new_path,
                    )
                else:
                    if not child.children:
                        # this is a property
                        fields_to_include[child.name] = name_to_return
                    else:
                        # this is either a BaseModel or a list of BaseModel
                        proms_map[name_to_return] = self.resolve_node_s(
                            node=child,
                            path=new_path,
                            model_s=getattr(model, child.name),
                        )

        # now gather the await-ables
        if proms_map:
            vals = await asyncio.gather(*proms_map.values(), return_exceptions=True)
            for name, val in zip(proms_map.keys(), vals):
                if isinstance(val, Exception):
                    if isinstance(val, GQLError):
                        self.errors.append(val)
                    else:
                        # do not expose this error to client
                        # include stack trace and send to sentry
                        node_that_errored = node_from_path(
                            node=node,
                            path=[name],
                            use_field_to_use=True,
                        )
                        self.errors.append(
                            GQLError(
                                message="Internal Server Error",
                                node=node_that_errored,
                                original_error=val,
                                path=(*path, name),
                            )
                        )
                        traceback.print_exception(val)
                    val = None
                final_d[name] = val
        model_d = model.model_dump(mode="json", include=set(fields_to_include))
        for name, name_to_use in fields_to_include.items():
            final_d[name_to_use] = model_d[name]
            if name_to_use != name:
                final_d[name] = model_d[name]

        # now null check and order property
        sorted_d = {}
        for name_to_return, name in name_to_return_to_display_name.items():
            val = final_d[name_to_return]
            if val is None:
                if path:
                    if self.is_not_nullable_map[model.gql_type_name()][name]:
                        # get the actual node from the path
                        null_node = node_from_path(
                            node=node, path=[name_to_return], use_field_to_use=True
                        )
                        full_path_to_error = (*path, name_to_return)
                        self.errors.append(
                            GQLError(
                                message=f"Cannot return null for non-nullable field {'.'.join(full_path_to_error)}",
                                path=full_path_to_error,
                                node=null_node,
                            )
                        )
                        return None
            sorted_d[name_to_return] = val
        del final_d
        return sorted_d

    async def resolve_root_nodes(
        self,
        root_nodes: list[M.OperationNode],
        operation_type_to_model: dict[M.OperationType, GQL | None],
    ) -> dict[str, T.Any]:
        proms = []
        for root_node in root_nodes:
            model = operation_type_to_model[root_node.type]
            if not model:
                raise Exception(f"{root_node.type} type required.")
            proms.append(
                self.resolve_node(
                    node=root_node,
                    model=operation_type_to_model[root_node.type],
                    path=(),
                )
            )
        d_list = await asyncio.gather(*proms)
        final_d = {}
        for d in d_list:
            final_d.update(d)
        return final_d
