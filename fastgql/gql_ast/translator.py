import typing as T
import graphql
from graphql.type.definition import GraphQLNullableType
from .models import (
    FieldNode,
    FieldNodeModel,
    FieldNodeMethod,
    FieldNodeField,
    OperationNode,
    OperationType,
    InlineFragmentNode,
    Argument,
)


class Translator:
    def __init__(
        self,
        document: graphql.DocumentNode,
        schema: graphql.GraphQLSchema,
        use_camel_case: bool,
    ):
        self.document = document
        self.schema = schema
        self.use_camel_case = use_camel_case
        self.query_definitions: list[graphql.OperationDefinitionNode] = []
        self.mutation_definitions: list[graphql.OperationDefinitionNode] = []
        self.subscription_definitions: list[graphql.OperationDefinitionNode] = []
        self.fragment_definitions: dict[str, graphql.FragmentDefinitionNode] = {}

    def to_snake(self, s: str) -> str:
        # TODO confirm that the node actually does require this
        if self.use_camel_case:
            return graphql.pyutils.camel_to_snake(s)
        return s

    def parse_val(self, val: graphql.ValueNode) -> T.Any:
        if isinstance(val, graphql.VariableNode):
            return val
        if isinstance(val, graphql.IntValueNode):
            return int(val.value)
        if isinstance(val, graphql.FloatValueNode):
            return float(val.value)
        if isinstance(val, graphql.StringValueNode):
            return val.value
        if isinstance(val, graphql.BooleanValueNode):
            return bool(val.value)
        if isinstance(val, graphql.ObjectValueNode):
            return {
                field.name.value: self.parse_val(field.value) for field in val.fields
            }
        if isinstance(val, graphql.ListValueNode):
            return [self.parse_val(v) for v in val.values]
        if isinstance(val, graphql.NullValueNode):
            return None
        # TODO for enums, lists... might need to use pydantic validate call here...anoying w return types and all
        return val.value

    @staticmethod
    def combine_sels(
        a: graphql.InlineFragmentNode | graphql.FieldNode,
        b: graphql.InlineFragmentNode | graphql.FieldNode,
    ) -> graphql.InlineFragmentNode | graphql.FieldNode:
        new_node: graphql.InlineFragmentNode | graphql.FieldNode = a.__copy__()
        if isinstance(a, graphql.FieldNode):
            new_node.arguments = (*a.arguments, *b.arguments)
        if not new_node.selection_set:
            new_node.selection_set = graphql.SelectionNode()
        new_node.selection_set.selections = (
            *(a.selection_set.selections if a.selection_set else []),
            *(b.selection_set.selections if b.selection_set else []),
        )
        return new_node

    def children_from_node(
        self,
        gql_field: graphql.GraphQLField | graphql.GraphQLObjectType,
        node: graphql.FieldNode | graphql.InlineFragmentNode,
        path_to_children: tuple[str, ...],
    ) -> list[FieldNode | InlineFragmentNode] | None:
        if node.selection_set is None:
            return None
        children: list[FieldNode | InlineFragmentNode] = []
        root_field = self.get_root_type(type_=gql_field)
        selection_q = [*node.selection_set.selections]

        # first, flatten and combine them
        has_seen: dict[str, graphql.InlineFragmentNode | graphql.FieldNode] = {}
        while len(selection_q) > 0:
            sel = selection_q.pop(0)
            if isinstance(sel, graphql.FragmentSpreadNode):
                frag = self.fragment_definitions[sel.name.value]
                selection_q.extend(frag.selection_set.selections)
                continue
            if isinstance(sel, graphql.FieldNode):
                key = sel.alias.value if sel.alias else sel.name.value
            elif isinstance(sel, graphql.InlineFragmentNode):
                key = sel.type_condition.name
            else:
                raise Exception(f"Invalid sel: {sel=}")
            if existing := has_seen.get(key):
                sel = self.combine_sels(existing, sel)
            has_seen[key] = sel

        for sel in has_seen.values():
            if isinstance(sel, graphql.InlineFragmentNode):
                gql_field = self.get_root_type(
                    root_field, type_condition=sel.type_condition.name.value
                )
            else:
                sel_name = sel.name.value
                if sel_name == "__typename":
                    gql_field = None
                else:
                    gql_field = root_field.fields[sel_name]
            child_s = self.from_node(
                gql_field=gql_field, node=sel, path=path_to_children
            )
            children.extend(child_s if isinstance(child_s, list) else [child_s])
        return children

    # @cache #TODO cache but these models are not hashable...
    def get_root_type(
        self,
        type_: T.Union[
            GraphQLNullableType,
            graphql.GraphQLNonNull,
            graphql.GraphQLField,
            graphql.GraphQLUnionType,
        ],
        type_condition: str = None,
    ) -> graphql.GraphQLObjectType | tuple[graphql.GraphQLUnionType] | None:
        if hasattr(type_, "of_type"):
            return self.get_root_type(type_.of_type, type_condition=type_condition)
        if hasattr(type_, "type"):
            return self.get_root_type(type_.type, type_condition=type_condition)
        if type_condition:
            if hasattr(type_, "types"):
                types = [self.get_root_type(t) for t in type_.types]
                for t in types:
                    if t.name == type_condition:
                        return t
                raise Exception("Type condition was not found.")

        return type_

    def from_node(
        self,
        gql_field: graphql.GraphQLField | graphql.GraphQLObjectType | None,
        node: graphql.SelectionNode,
        path: tuple[str, ...],
    ) -> FieldNode | InlineFragmentNode | list[FieldNode | InlineFragmentNode]:
        """if this is a fragment, return many nodes"""
        if isinstance(node, graphql.FragmentSpreadNode):
            frag = self.fragment_definitions[node.name.value]
            return [
                self.from_node(
                    gql_field=gql_field,
                    node=sel,
                    path=path,
                )
                for sel in frag.selection_set.selections
            ]

        if not gql_field:
            annotation = None
        elif isinstance(gql_field, graphql.GraphQLObjectType):
            annotation = gql_field._pydantic_model
        else:
            annotation = gql_field.type._anno

        if isinstance(node, graphql.InlineFragmentNode):
            type_condition = node.type_condition.name.value
            return InlineFragmentNode(
                children=self.children_from_node(
                    gql_field=gql_field,
                    node=node,
                    path_to_children=(*path, type_condition),
                ),
                original_node=node,
                type_condition=type_condition,
                annotation=annotation,
            )
        elif isinstance(node, graphql.FieldNode):
            # build args
            arguments: list[Argument] = []
            for argument in node.arguments:
                arguments.append(
                    Argument(
                        display_name=argument.name.value,
                        name=self.to_snake(argument.name.value),
                        value=self.parse_val(argument.value),
                    )
                )
            alias = node.alias.value if node.alias else None
            name = self.to_snake(node.name.value)

            children = self.children_from_node(
                gql_field=gql_field,
                node=node,
                path_to_children=(*path, node.name.value),
            )
            display_name = node.name.value
            # gql_field_type = self.get_root_type(gql_field)
            if not gql_field:
                # this is __typename
                return FieldNode(
                    original_node=node,
                    children=children,
                    name=name,
                    alias=alias,
                    display_name=display_name,
                    arguments=arguments,
                    annotation=annotation,
                )
            gql_field_type = gql_field.type
            if hasattr(gql_field_type, "_field_info"):
                return FieldNodeField(
                    original_node=node,
                    children=children,
                    name=name,
                    alias=alias,
                    display_name=display_name,
                    arguments=arguments,
                    annotation=annotation,
                    field=gql_field_type._field_info,
                )
            elif hasattr(gql_field_type, "_method"):
                return FieldNodeMethod(
                    original_node=node,
                    children=children,
                    name=name,
                    alias=alias,
                    display_name=display_name,
                    arguments=arguments,
                    annotation=annotation,
                    method=gql_field_type._method,
                )
            else:
                root_type = self.get_root_type(gql_field)
                if isinstance(root_type, graphql.GraphQLUnionType):
                    models = [t._pydantic_model for t in root_type.types]
                else:
                    models = [root_type._pydantic_model]
                # otherwise, this will be an object type
                return FieldNodeModel(
                    original_node=node,
                    children=children,
                    name=name,
                    alias=alias,
                    display_name=display_name,
                    arguments=arguments,
                    models=models,
                    annotation=annotation,
                )
        else:
            raise Exception(f"Invalid node type: {type(node)=}, {node=}")

    def from_operation_node(
        self, node: graphql.OperationDefinitionNode
    ) -> OperationNode:
        # first, build children, and then their children
        children: list[FieldNode | InlineFragmentNode] = []
        # TODO possible inline frags?
        for sel in node.selection_set.selections:
            if node.operation == graphql.OperationType.MUTATION:
                gql_field = self.schema.mutation_type
            elif node.operation == graphql.OperationType.QUERY:
                gql_field = self.schema.query_type
            else:
                raise Exception(f"Unimplemented operation type: {node.operation=}")
            child_s = self.from_node(
                gql_field=gql_field.fields[sel.name.value],
                node=sel,
                path=(node.operation.value,),
            )
            if type(child_s) is list:
                children.extend(child_s)
            else:
                children.append(child_s)

        op = OperationNode(
            name=node.name.value if node.name else None,
            type=OperationType(node.operation.value),
            children=children,
            original_node=node,
        )

        return op

    def translate(self) -> list[OperationNode]:
        for definition in self.document.definitions:
            if isinstance(definition, graphql.FragmentDefinitionNode):
                self.fragment_definitions[definition.name.value] = definition
            elif isinstance(definition, graphql.OperationDefinitionNode):
                if definition.operation == graphql.OperationType.QUERY:
                    self.query_definitions.append(definition)
                elif definition.operation == graphql.OperationType.MUTATION:
                    self.mutation_definitions.append(definition)
                else:
                    self.subscription_definitions.append(definition)
            else:
                raise Exception(
                    f"Unknown type of definition: {definition=}, {type(definition)=}"
                )

        # start with the operations
        op_nodes: list[OperationNode] = []
        for operation in [*self.query_definitions, *self.mutation_definitions]:
            op_nodes.append(self.from_operation_node(operation))
        return op_nodes
