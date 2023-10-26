import typing as T
from enum import Enum
import random
import string
import re
from pydantic import BaseModel, Field


class FilterConnector(str, Enum):
    AND = "AND"
    OR = "OR"


class QueryBuilderError(Exception):
    pass


class ChildEdge(BaseModel):
    # for example, .artists
    db_expression: str | None
    qb: "QueryBuilder"


class QueryBuilder(BaseModel):
    typename: str | None = None
    fields: set[str] = Field(default_factory=set)
    variables: dict[str, T.Any] = Field(default_factory=dict)
    children: dict[str, ChildEdge] = Field(default_factory=dict)
    filter: str | None = None
    order_by: str | None = None
    offset: str | None = None
    limit: str | None = None

    full_query_str: str | None = None
    pattern_to_replace: str | None = None

    @staticmethod
    def build_child_var_name(
        child_name: str, var_name: str, variables_to_use: dict[str, T.Any]
    ) -> str:
        child_name = re.sub(r"[^a-zA-Z0-9]+", "_", child_name)
        count = 0
        while var_name in variables_to_use:
            count_str = "" if not count else f"_{count}"
            var_name = f"_{child_name}{count_str}_{var_name}"
        return var_name

    def build(self) -> tuple[str, dict[str, T.Any]]:
        variables_to_use = self.variables.copy()
        child_strs: set[str] = set()
        for child_name, child_edge in self.children.items():
            child = child_edge.qb
            child_str, child_variables = child.build()
            for var_name, var_val in child_variables.items():
                if var_name in variables_to_use:
                    if var_val is variables_to_use[var_name]:
                        continue
                    # must change the name for the child
                    new_var_name = self.build_child_var_name(
                        child_name=child_name,
                        var_name=var_name,
                        variables_to_use=variables_to_use,
                    )
                    variables_to_use[new_var_name] = var_val
                    # now, must regex the str to find this and replace it
                    regex = re.compile(r"\${}(?!\w)".format(var_name))
                    child_str = regex.sub(f"${new_var_name}", child_str)
                else:
                    variables_to_use[var_name] = var_val
            if not child_edge.db_expression:
                child_str = f"{child_name}: {child_str}"
            else:
                child_str = (
                    f"{child_name} := (select {child_edge.db_expression} {child_str})"
                )
            child_strs.add(child_str)

        fields_str = ", ".join([*sorted(self.fields), *sorted(child_strs)])
        s_parts = ["" if not fields_str else f"{{ {fields_str} }}"]
        if self.filter:
            s_parts.append(f"FILTER {self.filter}")
        if self.order_by:
            s_parts.append(f"ORDER BY {self.order_by}")
        if self.offset is not None:
            s_parts.append(self.offset)
        if self.limit is not None:
            s_parts.append(self.limit)
        final_s = " ".join(s_parts)
        if self.full_query_str:
            final_s = self.full_query_str.replace(self.pattern_to_replace, final_s)
        return final_s, variables_to_use

    def add_variable(
        self, key: str, val: T.Any, replace: bool = False
    ) -> "QueryBuilder":
        if key in self.variables:
            if not replace and self.variables[key] != val:
                raise QueryBuilderError(
                    f"Key {key} already exists in variables so you cannot add it. "
                    f"If you'd like to replace it, pass replace."
                )
        self.variables[key] = val
        return self

    def add_variables(
        self, variables: dict[str, T.Any], replace: bool = False
    ) -> "QueryBuilder":
        """if there is an error, it does not save to the builder"""
        if not variables:
            return self
        if not replace:
            for k in variables.keys():
                if k in self.variables:
                    raise QueryBuilderError(
                        f"Key {k} already exists in variables so you cannot add it. "
                        f"If you'd like to replace it, pass replace."
                    )
        self.variables.update(variables)
        return self

    # ADD HELPER FUNCTIONS FOR LIMIT AND OFFSET -> like add_offset...
    def set_offset(self, offset: int | None, replace: bool = False) -> "QueryBuilder":
        if offset is None:
            return self
        if self.offset is not None:
            if not replace:
                raise QueryBuilderError(
                    "An offset already exists. If you would like to replace it, pass in replace."
                )
        self.offset = "OFFSET <int32>$offset"
        self.add_variable("offset", offset, replace=replace)
        return self

    def set_limit(self, limit: int | None, replace: bool = False) -> "QueryBuilder":
        if limit is None:
            return self
        if self.limit is not None:
            if not replace:
                raise QueryBuilderError(
                    "A limit already exists. If you would like to replace it, pass in replace."
                )
        self.limit = "LIMIT <int32>$limit"
        self.add_variable("limit", limit, replace=replace)
        return self

    # needs to be add_filter and add_order_by

    def set_filter(
        self,
        filter: str,
        variables: dict[str, T.Any] | None = None,
        replace_filter: bool = False,
        replace_variables: bool = False,
    ) -> "QueryBuilder":
        if self.filter and not replace_filter:
            raise QueryBuilderError("Filter already exists.")
        self.add_variables(variables=variables, replace=replace_variables)
        self.filter = filter
        return self

    def set_order_by(
        self,
        order_by: str,
        variables: dict[str, T.Any] | None = None,
        replace_order_by: bool = False,
        replace_variables: bool = False,
    ) -> "QueryBuilder":
        if self.order_by and not replace_order_by:
            raise QueryBuilderError("Order by already exists.")
        self.add_variables(variables=variables, replace=replace_variables)
        self.order_by = order_by
        return self

    def set_full_query_str(
        self,
        full_query_str: str,
        replace: bool = False,
        variables: dict[str, T.Any] | None = None,
        replace_variables: bool = False,
    ) -> "QueryBuilder":
        if self.full_query_str and not replace:
            raise QueryBuilderError("full_query_str already exists.")
        self.add_variables(variables=variables, replace=replace_variables)
        pattern_to_replace = "".join(
            random.choice(string.ascii_letters + string.digits) for _ in range(10)
        )
        self.full_query_str = full_query_str.replace("$$", pattern_to_replace)
        self.pattern_to_replace = pattern_to_replace
        return self
