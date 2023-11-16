import typing as T
from enum import Enum
import random
import string
import re
from pydantic import BaseModel, Field
import sqlparse


class FilterConnector(str, Enum):
    AND = "AND"
    OR = "OR"


class QueryBuilderError(Exception):
    pass


class Cardinality(str, Enum):
    ONE = "ONE"
    MANY = "MANY"


class ChildEdge(BaseModel):
    qb: "QueryBuilder"
    name: str
    from_where: str


class Selection(BaseModel):
    alias: str
    path: str
    variables: dict[str, T.Any] | None = None


class QueryBuilder(BaseModel):
    table_name: str
    # table_alias: str
    cardinality: Cardinality
    selections: list[Selection] = Field(default_factory=list)
    variables: dict[str, T.Any] = Field(default_factory=dict)
    children: list[ChildEdge] = Field(default_factory=list)

    join: str | None = None
    where: str | None = None
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

    def set_offset(self, offset: int | None, replace: bool = False) -> "QueryBuilder":
        if offset is None:
            return self
        if self.offset is not None:
            if not replace:
                raise QueryBuilderError(
                    "An offset already exists. If you would like to replace it, pass in replace."
                )
        self.offset = "OFFSET $offset"
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
        self.limit = "LIMIT $limit"
        self.add_variable("limit", limit, replace=replace)
        return self

    def prepend_where(self, where: str) -> "QueryBuilder":
        where_s = where
        if self.where:
            where_s = f"{where_s} AND ({self.where})"
        self.where = where_s
        return self

    def set_where(
        self,
        where: str,
        variables: dict[str, T.Any] | None = None,
        replace_where: bool = False,
        replace_variables: bool = False,
    ) -> "QueryBuilder":
        if self.where and not replace_where:
            raise QueryBuilderError("Where already exists.")
        self.add_variables(variables=variables, replace=replace_variables)
        self.where = where
        return self

    def set_join(
        self,
        join: str,
        variables: dict[str, T.Any] | None = None,
        replace_join: bool = False,
        replace_variables: bool = False,
    ) -> "QueryBuilder":
        if self.join and not replace_join:
            raise QueryBuilderError("Join already exists.")
        self.add_variables(variables=variables, replace=replace_variables)
        self.join = join
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

    def build_child(
        self,
        edge: "ChildEdge",
        path: tuple[str, ...],
        parent_table_alias: str,
        variables: dict,
    ) -> str:
        s, v = edge.qb.build(
            from_where=edge.from_where, parent_table_alias=parent_table_alias, path=path
        )
        for var_name, var_val in v.items():
            if var_name in variables:
                if var_val is variables[var_name]:
                    continue
                # must change the name for the child
                new_var_name = self.build_child_var_name(
                    child_name=edge.name,
                    var_name=var_name,
                    variables_to_use=variables,
                )
                variables[new_var_name] = var_val
                # now, must regex the str to find this and replace it
                regex = re.compile(r"\${}(?!\w)".format(var_name))
                s = regex.sub(f"${new_var_name}", s)
            else:
                variables[var_name] = var_val

        s = f"'{edge.name}', ({s})"
        return s

    def build(
        self,
        from_where: str | None,
        parent_table_alias: str | None,
        path: tuple[str, ...] | None,
        order_fields_alphabetically: bool = True,
    ) -> tuple[str, dict[str, T.Any]]:
        if path:
            new_path = (*path, self.table_name)
        else:
            new_path = (self.table_name,)
        table_alias = "__".join(new_path).replace('"', "")
        if not path:
            if table_alias.lower() == self.table_name.lower().replace('"', ""):
                table_alias = f"_{table_alias}"
        variables = self.variables.copy()
        child_strs = [
            self.build_child(
                edge=child_edge,
                path=new_path,
                variables=variables,
                parent_table_alias=table_alias,
            )
            for child_edge in self.children
        ]
        selection_strs = [f"'{sel.alias}', {sel.path}" for sel in self.selections]
        all_fields_strs = [*selection_strs, *child_strs]
        if order_fields_alphabetically:
            all_fields_strs.sort()
        if not all_fields_strs:
            raise Exception(f"Query Builder {self=} has no fields.")
        fields_s = ", ".join(all_fields_strs)
        where_str = self.where
        if from_where:
            if self.where:
                where_str = f"{from_where} AND {self.where}"
            else:
                where_str = from_where
        filter_parts: list[str] = []
        if self.join:
            filter_parts.append(f"{self.join}")
        if where_str:
            if "where" not in where_str.lower():
                where_str = f"WHERE {where_str}"
            filter_parts.append(f"{where_str}")
        if self.order_by:
            filter_parts.append(f"ORDER BY {self.order_by}")
        if self.offset:
            filter_parts.append(self.offset)
        if self.limit:
            filter_parts.append(self.limit)
        filter_parts_s = "\n".join(filter_parts)
        # TODO re from -> not sure if this is the right thing... want something more sturdy
        if "from" not in filter_parts_s.lower():
            from_line = f"FROM {self.table_name} {table_alias}"
        else:
            from_line = ""
        s = f"""
SELECT json_build_object(
    {fields_s}
) AS {table_alias}_json
{from_line}
{filter_parts_s}
""".strip()
        if self.cardinality == Cardinality.MANY:
            s = f"""
SELECT json_agg({table_alias}_json) AS {table_alias}_json_agg
FROM (
    {s}
) as {table_alias}_json_sub
            """.strip()
        # now replace the values
        s = s.replace("$current", table_alias)
        if parent_table_alias:
            s = s.replace("$parent", parent_table_alias)
        return s, variables

    def build_root(
        self,
        format_sql: bool = False,
        order_fields_alphabetically: bool = False,
        from_where: str = None,
        parent_table_alias: str = None,
        path: tuple[str, ...] = None,
    ) -> tuple[str, list[T.Any]]:
        rr = self.build(
            order_fields_alphabetically=order_fields_alphabetically,
            from_where=from_where,
            parent_table_alias=parent_table_alias,
            path=path,
        )
        s, v = rr
        if v:
            s, v_list = self.prepare_query(sql=s, params=v)
        else:
            v_list = []
        if format_sql:
            s = sqlparse.format(s, reindent=True, keyword_case="upper")
        return s, v_list

    @staticmethod
    def prepare_query(sql: str, params: dict[str, T.Any]) -> tuple[str, list[T.Any]]:
        """
        Generated by GPT4
        Converts a SQL string with named parameters (e.g., $variable) to a format
        compatible with asyncpg (using $1, $2, etc.), and returns the new SQL string
        and the list of values in the correct order.

        :param sql: Original SQL string with named parameters
        :param params: Dictionary of parameters
        :return: Tuple of (new_sql_string, list_of_values)
        """

        # Extract the named parameters from the SQL string
        named_params = re.findall(r"\$(\w+)", sql)
        # Ensure that each parameter is unique
        unique_params = list(dict.fromkeys(named_params))

        # Replace named parameters with positional parameters ($1, $2, etc.)
        for i, param in enumerate(unique_params, start=1):
            sql = sql.replace(f"${param}", f"${i}")

        # Create the list of values in the order they appear in the query
        values = [params[param] for param in unique_params]

        return sql, values

    def sel(
        self, alias: str, path: str = None, variables: dict[str, T.Any] | None = None
    ) -> "QueryBuilder":
        self.add_variables(variables)
        if not path:
            path = f"$current.{alias}"
        self.selections.append(Selection(alias=alias, path=path, variables=variables))
        return self

    def add_sel(self, sel: Selection) -> "QueryBuilder":
        return self.sel(alias=sel.alias, path=sel.path, variables=sel.variables)

    def add_child(
        self, child: "QueryBuilder", alias: str, from_where: str
    ) -> "QueryBuilder":
        self.children.append(ChildEdge(qb=child, name=alias, from_where=from_where))
        return self
