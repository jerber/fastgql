import pathlib
import json
from fastgql.gql_ast import models as M


def node_from_path(
    node: M.FieldNode, path: list[str], use_field_to_use: bool = False
) -> M.FieldNode | None:
    if not path:
        return node
    current_val = path.pop(0)
    children_q = [*node.children]
    while len(children_q) > 0:
        child = children_q.pop(0)
        if isinstance(child, M.FieldNode):
            name = (
                child.name
                if not use_field_to_use
                else child.alias or child.display_name
            )
            if name == current_val:
                return node_from_path(node=child, path=path)
        if isinstance(child, M.InlineFragmentNode):
            children_q.extend(child.children)

    return None


def get_graphiql_html(
    subscription_enabled: bool = True, replace_variables: bool = True
) -> str:
    here = pathlib.Path(__file__).parent
    path = here / "static/graphiql.html"

    template = path.read_text(encoding="utf-8")

    if replace_variables:
        template = template.replace(
            "{{ SUBSCRIPTION_ENABLED }}", json.dumps(subscription_enabled)
        )

    return template
