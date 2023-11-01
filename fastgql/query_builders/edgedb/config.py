import typing as T
import inspect
from dataclasses import dataclass
from pydantic import validate_call

from fastgql.info import Info
from fastgql.gql_ast import models as M
from fastgql.execute.utils import parse_value
from fastgql.utils import node_from_path
from .query_builder import QueryBuilder, ChildEdge


def combine_qbs(
    *qbs: QueryBuilder,
    nodes_to_include: list[
        M.FieldNode
    ],  # TODO so far, not needed but may for better inheritence
) -> QueryBuilder:
    """takes in a dict of db typename and qb"""
    new_qb = QueryBuilder()
    # add dangling to each qb
    for node in nodes_to_include:
        for qb in qbs:
            if node.name == "__typename":
                qb.fields.add(f"{node.alias or node.name} := .__type__.name")
            # TODO other things here
    for qb in qbs:
        if not qb.typename:
            raise Exception("QB must have a typename if it is to be combined.")
        new_qb.children[qb.typename] = ChildEdge(
            db_expression=f"[is {qb.typename}]", qb=qb
        )
    return new_qb


@dataclass
class Property:
    db_name: str | None
    update_qb: T.Callable[[QueryBuilder], T.Awaitable[None] | None] = None


@dataclass
class Link:
    db_name: str | None
    return_cls_qb_config: (
        T.Union["QueryBuilderConfig", dict[str, "QueryBuilderConfig"]] | None
    ) = None
    path_to_return_cls: tuple[str, ...] | None = None
    update_qbs: T.Callable[[..., T.Any], None] = None


@dataclass
class QueryBuilderConfig:
    properties: dict[str, Property]
    links: dict[str, Link]

    def is_empty(self) -> bool:
        return not self.properties and not self.links

    async def from_info(
        self, info: Info, node: M.FieldNode | M.InlineFragmentNode
    ) -> QueryBuilder | None:
        if not node:
            return None
        qb = QueryBuilder()
        children_q = [*node.children]
        while len(children_q) > 0:
            child = children_q.pop(0)
            if isinstance(child, M.InlineFragmentNode):
                children_q.extend(child.children)
            else:
                if child.name in self.properties:
                    property_config = self.properties[child.name]
                    if db_name := property_config.db_name:
                        if child.name != db_name:
                            qb.fields.add(f"{child.name} := .{db_name}")
                        else:
                            qb.fields.add(db_name)
                    if update_qb := property_config.update_qb:
                        _ = update_qb(qb)
                        if inspect.isawaitable(_):
                            await _
                if child.name in self.links:
                    method_config = self.links[child.name]
                    original_child = child
                    if method_config.path_to_return_cls:
                        child = node_from_path(
                            node=child, path=[*method_config.path_to_return_cls]
                        )
                    if config := method_config.return_cls_qb_config:
                        if isinstance(config, dict):
                            dangling_children: list[M.FieldNode] = []
                            frag_qbs: list[QueryBuilder] = []
                            for child_child in child.children:
                                if isinstance(child_child, M.InlineFragmentNode):
                                    child_child_qb = await config[
                                        child_child.type_condition
                                    ].from_info(info=info, node=child_child)
                                    child_child_qb.typename = child_child.type_condition
                                    frag_qbs.append(child_child_qb)
                                elif isinstance(child_child, M.FieldNode):
                                    dangling_children.append(child_child)
                                else:
                                    raise Exception(
                                        f"Invalid node for config as dict: {child=}"
                                    )
                            # now combine the dangling with the frags
                            child_qb = combine_qbs(
                                *frag_qbs, nodes_to_include=dangling_children
                            )
                            child_qb.fields.add("typename := .__type__.name")
                        else:
                            child_qb = await config.from_info(info=info, node=child)
                        if db_name := method_config.db_name:
                            name_to_use = child.alias or child.name
                            db_expression = (
                                None if name_to_use == db_name else f".{db_name}"
                            )
                            qb.children[name_to_use] = ChildEdge(
                                db_expression=db_expression, qb=child_qb
                            )
                        if update_qbs := method_config.update_qbs:
                            kwargs = {
                                "qb": qb,
                                "child_qb": child_qb,
                                "child": child,
                                "info": info,
                                **{
                                    a.name: parse_value(
                                        variables=info.context.variables, v=a.value
                                    )
                                    for a in original_child.arguments
                                },
                            }
                            kwargs = {
                                k: v
                                for k, v in kwargs.items()
                                if k in inspect.signature(update_qbs).parameters
                            }
                            _ = validate_call(update_qbs(**kwargs))
                            if inspect.isawaitable(_):
                                await _
        return qb
