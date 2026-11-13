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

A failed source's stored error becomes one plain sentence about "This site".
"""

import pytest

from app.knowledge.failure_advice import FAILURE_ADVICE, GENERIC_REASON, plain_reason

URL = "https://erfanpv.com"


@pytest.mark.parametrize("cause", list(FAILURE_ADVICE))
def test_our_advice_is_rephrased_about_this_site(cause):
    reason = plain_reason(FAILURE_ADVICE[cause].format(url=URL), URL)
    assert reason.startswith("This site ")
    assert URL not in reason


@pytest.mark.parametrize("error,source", [
    ("Traceback (most recent call last): KeyError 'x'", URL),
    (FAILURE_ADVICE[next(iter(FAILURE_ADVICE))].format(url="https://other.com"), URL),
    (None, URL),
    ("", URL),
    ("anything", None),
])
def test_anything_else_gets_the_generic_reason(error, source):
    assert plain_reason(error, source) == GENERIC_REASON
