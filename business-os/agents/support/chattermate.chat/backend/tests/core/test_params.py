"""
Copyright 2024-2026 ChatterMate

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.params import MAX_DB_INT, MAX_PAGE, DbIntId, PageNumber

app = FastAPI()


@app.get("/things/{thing_id}")
def read_thing(thing_id: DbIntId, page: PageNumber = 1):
    return {"thing_id": thing_id, "page": page}


client = TestClient(app)


def test_ids_the_database_can_hold_pass_through():
    assert client.get(f"/things/{MAX_DB_INT}?page={MAX_PAGE}").json() == {"thing_id": MAX_DB_INT, "page": MAX_PAGE}


def test_ids_and_pages_the_database_would_choke_on_are_422():
    """Past Postgres INTEGER, or a page whose OFFSET overflows, the query itself
    would fail with a 500; the request is refused up front instead."""
    assert client.get(f"/things/{MAX_DB_INT + 1}").status_code == 422
    assert client.get("/things/0").status_code == 422
    assert client.get(f"/things/1?page={MAX_PAGE + 1}").status_code == 422
    assert client.get("/things/1?page=0").status_code == 422
