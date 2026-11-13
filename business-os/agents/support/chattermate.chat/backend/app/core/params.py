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

# Request parameters with the bounds the database implies. An integer id past
# Postgres INTEGER, or a negative LIMIT, makes the query itself fail — a 500 —
# where the caller should get a 422 (or simply nothing found).

from typing import Annotated

from fastapi import Path, Query

MAX_DB_INT = 2_147_483_647

# An integer primary key in the URL path.
DbIntId = Annotated[int, Path(ge=1, le=MAX_DB_INT)]

# A 1-based page number; far past any real list, short of overflowing the OFFSET.
MAX_PAGE = 100_000
PageNumber = Annotated[int, Query(ge=1, le=MAX_PAGE)]
