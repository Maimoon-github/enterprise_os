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

The crawler says who it is, the same way everywhere it fetches - and a site
that refuses it gets advice that says so, not a guess about bot protection.
"""

import inspect

from app.knowledge import crawl4ai_fallback
from app.knowledge.crawler_identity import CRAWLER_USER_AGENT
from app.knowledge.enhanced_website_reader import EnhancedWebsiteReader
from app.knowledge.failure_advice import FAILURE_ADVICE, FailureCause, plain_reason


def test_identifies_honestly_by_name():
    assert "ChatterMateBot" in CRAWLER_USER_AGENT
    assert "Chrome/" not in CRAWLER_USER_AGENT  # the stale fake that WordPress.com refuses


def test_reader_sends_the_shared_identity():
    reader = EnhancedWebsiteReader()
    assert reader.user_agent == CRAWLER_USER_AGENT
    assert reader.headers["User-Agent"] == CRAWLER_USER_AGENT


def test_browser_fallback_uses_the_shared_identity():
    source = inspect.getsource(crawl4ai_fallback)
    assert "Chrome/120" not in source
    assert source.count("user_agent=CRAWLER_USER_AGENT") == 2  # both browser paths


def test_a_refusal_reads_as_a_refusal():
    url = "https://chattermate.chat"
    reason = plain_reason(FAILURE_ADVICE[FailureCause.BOT_BLOCKED].format(url=url), url)
    assert reason.startswith("This site refused our crawler.")
    assert "challenge page" not in reason
