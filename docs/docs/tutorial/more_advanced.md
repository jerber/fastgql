# Advanced Tutorial

The reason I built **FastGQL** was to address the `n+1` problem I had with other frameworks.

Consider this working example using [`EdgeDB`](https://edgedb.com) as the database:

<details>
<summary>Full file 👀</summary>

```Python
{!./docs_src/tutorial/movies_edgedb.py!}
```

</details>

For each connection, we have to make a new query. For example, if your query is:

```graphql
{
  accountByUsername(username: "Cameron") {
    id
    username
    watchlist(limit: 100) {
      __typename
      ...on Movie {
        id
        title
        releaseYear
        actors {
          name
        }
      }
      ... on Show {
        id
        title
      }
    }
  }
}
```

You get back a lot of nested data. For each nested data you get, that's another database call. For example, to get actors from a movie:

```python
class Content(GQLInterface):
    id: UUID
    title: str

    async def actors(self) -> list["Person"]:
        q = """select Content { actors: { id, name } } filter .id = <uuid>$id"""
        content_d = await query_required_single_json(
            name="content.actors", query=q, id=self.id
        )
        return [Person(**p) for p in content_d["actors"]]
```

So, to execute this query, the server had to:
1) get the account by username from the database,
2) get the watchlist of that user from the database,
3) get the actor of each movie from the database

There are some solutions to make this process more efficient. One of them is using [dataloaders](https://xuorig.medium.com/the-graphql-dataloader-pattern-visualized-3064a00f319f).

However, even with a dataloader, you are still making new requests to the database for each new level of data you are requesting.

**FastGQL** comes with a way to solve this problem. It ships with `QueryBuilder` functionality. This allows you to map your GraphQL schema to your database schema, which means you can dynamically generate the exact database query you need to fulfill the client's request.

!!! note
    Currently `QueryBuilder` only works with `EdgeDB`.

Here is a full example of the same schema, now using the `QueryBuilder` feature.

<details>
<summary>Full file 👀</summary>

```Python
{!./docs_src/tutorial/movies_qb.py!}
```

</details>

Now this same query:
```graphql
{
  accountByUsername(username: "Cameron") {
    id
    username
    watchlist(limit: 100) {
      __typename
      ...on Movie {
        id
        title
        releaseYear
        actors {
          name
        }
      }
      ... on Show {
        id
        title
      }
    }
  }
}
```
executes with only one call to the database that looks like this:
```
select Account { id, username, watchlist: { typename := .__type__.name, Movie := (select [is Movie] { __typename := .__type__.name, id, release_year, title, actors: { name } }), Show := (select [is Show] { __typename := .__type__.name, id, title }) } LIMIT <int32>$limit } filter .username = <str>$username
```

The original query took around 180ms to execute and make 6 database calls.

The new query using `QueryBuilders` takes less than 30ms to execute and only makes one database call!

For this small example, the results are not so dramatic. But in production, on large datasets, the speed advantage can easily be 10x.