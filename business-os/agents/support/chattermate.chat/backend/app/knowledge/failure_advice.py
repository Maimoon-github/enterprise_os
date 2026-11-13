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

What to tell someone when a knowledge source couldn't be read: one piece of
advice per failure cause. Kept apart from the crawler so code that only needs
the words doesn't import the crawling stack.
"""

from typing import Optional


class SourceUnreadable(Exception):
    """The source itself couldn't be read: the customer's site, not a bug of
    ours. Its message is the advice the user sees, so it's reported to them and
    logged as a warning, not counted as an application error."""


class FailureCause:
    """Why a page could not be read.

    The old message offered the user three guesses at once ("empty, require
    JavaScript, or be unreachable"). _process_url always knew which one it hit;
    it just threw the answer away. These are the classes it can tell apart, and
    each one gets its own advice in FAILURE_ADVICE below.
    """

    DNS = "dns"
    CONNECTION = "connection"
    TIMEOUT = "timeout"
    BOT_BLOCKED = "bot_blocked"
    HTTP_ERROR = "http_error"
    EMPTY_RESPONSE = "empty_response"
    THIN_CONTENT = "thin_content"
    BLOCKED_HOST = "blocked_host"
    NOT_A_PAGE = "not_a_page"
    # A sign-in or admin page, or a store that isn't open to visitors yet
    LOGIN_REQUIRED = "login_required"
    # Something that is not a transport failure at all — most likely a bug of
    # ours. Deliberately has no entry in FAILURE_ADVICE: we fall back to the
    # generic message rather than blame the customer's site for our crash.
    UNKNOWN = "unknown"
    # The source as a whole, not one page: it ran past its time limit, or its
    # worker died partway (the queue item was left 'processing').
    TOO_LONG = "too_long"
    INTERRUPTED = "interrupted"


# What to tell the user for each cause. Phrased as "what happened, what to do".
FAILURE_ADVICE = {
    FailureCause.DNS: (
        "{url} could not be found — the domain does not resolve. Check the "
        "address for typos, and that the site is published."
    ),
    FailureCause.CONNECTION: (
        "{url} refused the connection. Check the site is online and reachable "
        "from the public internet."
    ),
    FailureCause.TIMEOUT: (
        "{url} did not respond in time. If the site is usually slow, try again "
        "in a few minutes, or add a specific page instead of the whole site."
    ),
    FailureCause.BOT_BLOCKED: (
        "{url} refused our crawler. Add the content manually with Upload PDF "
        "or Paste text."
    ),
    FailureCause.HTTP_ERROR: (
        "{url} returned an error response. Check the URL is correct and "
        "publicly accessible, then try again."
    ),
    FailureCause.EMPTY_RESPONSE: (
        "{url} returned an empty page. Check the site is published and serving "
        "content at that address."
    ),
    FailureCause.THIN_CONTENT: (
        "{url} loaded but had almost no readable text — it may render its "
        "content with JavaScript we could not run. Add the content manually "
        "with Upload PDF or Paste text."
    ),
    FailureCause.BLOCKED_HOST: (
        "{url} redirected to an address we are not allowed to fetch. Use the "
        "site's public URL."
    ),
    FailureCause.NOT_A_PAGE: (
        "{url} is a file, not a web page. Add a PDF with Upload PDF, or add "
        "the page that links to it."
    ),
    FailureCause.LOGIN_REQUIRED: (
        "{url} asks for a password: it's a sign-in or admin page, or a store "
        "that isn't open to visitors yet. Add your site's public address "
        "instead, like yourstore.com."
    ),
    FailureCause.TOO_LONG: (
        "{url} took too long to read. Add specific pages instead of the whole "
        "site, or add the content with Upload PDF or Paste text."
    ),
    FailureCause.INTERRUPTED: (
        "{url} could not be read to the end: our reader stopped partway. Add "
        "it again to retry, or add specific pages instead of the whole site."
    ),
}


GENERIC_REASON = (
    "We couldn't read any pages there. Try a specific page, or paste text or "
    "upload a PDF instead."
)


def plain_reason(error: Optional[str], source: Optional[str]) -> str:
    """The stored failure for `source`, phrased about "This site" (the email
    or page already shows the address). Anything that isn't one of our own
    advice messages - a raw exception, say - becomes GENERIC_REASON rather
    than leak internals to the customer."""
    if error and source:
        for advice in FAILURE_ADVICE.values():
            if error == advice.format(url=source):
                return advice.format(url="This site")
    return GENERIC_REASON
