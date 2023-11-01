from uuid import uuid4, UUID

people = [
    {"id": uuid4(), "name": "Margot Robbie"},
    {"id": uuid4(), "name": "Ryan Gosling"},
    {"id": uuid4(), "name": "Jeremy Allen White"},
]
movies = [
    {"id": uuid4(), "title": "Barbie", "release_year": 2023, "actors": people[0:2]}
]
shows = [
    {
        "id": uuid4(),
        "title": "Game Of Thrones",
        "seasons": [{"id": uuid4(), "number": x} for x in range(1, 9)],
        "actors": people[2:],
    }
]
content = [*movies, *shows]
content_by_person_id = {}
for p in people:
    person_id = p["id"]
    filmography = []
    for c in content:
        if person_id in [c_actor["id"] for c_actor in c["actors"]]:
            filmography.append(c)
    content_by_person_id[person_id] = filmography
movies_by_id: dict[UUID, dict] = {m["id"]: m for m in movies}
shows_by_id: dict[UUID, dict] = {s["id"]: s for s in shows}
content_by_id: dict[UUID, dict] = {c["id"]: c for c in content}
accounts = [{"id": uuid4(), "username": "jeremy", "watchlist": content}]
accounts_by_username = {a["username"]: a for a in accounts}
