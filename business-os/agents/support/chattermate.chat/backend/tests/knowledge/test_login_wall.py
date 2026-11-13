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

Pages that ask for a password are not knowledge.
"""

import pytest
from bs4 import BeautifulSoup

from app.knowledge.login_wall import MAX_TEXT_ON_A_LOGIN_PAGE, is_auth_path, looks_like_login_wall

# What a Shopify store that isn't open yet serves (trimmed from a real one)
SHOPIFY_NOT_OPEN = """
<html><body>
  <h1>My Store 3</h1><p>Opening soon</p>
  <p>Sign up for our newsletter to be the first to know when we launch.</p>
  <form action="/password" method="post"><input type="password" name="password"><button>Enter</button></form>
  <p>This shop will be powered by Shopify</p>
</body></html>
"""


def page(html):
    return BeautifulSoup(html, "html.parser")


@pytest.mark.parametrize("url", [
    "https://shop.myshopify.com/admin",
    "https://shop.myshopify.com/admin/products/1",
    "https://site.com/admin",
    "https://site.com/auth/",
    "https://site.com/account/login",
    "https://site.com/login",
    "https://site.com/password",
    "https://site.com/wp-admin/",
    "https://site.com/wp-login.php",
    "https://site.com/Sign-In",
])
def test_sign_in_and_admin_paths(url):
    assert is_auth_path(url)


@pytest.mark.parametrize("url", [
    "https://site.com",
    "https://site.com/",
    "https://site.com/administration-services",
    "https://site.com/blog/how-to-login-faster",
    "https://site.com/authors",
    "https://site.com/products/password-manager",
    # Public docs that happen to live under /admin or /auth
    "https://docs.site.com/admin/configure-sso",
    "https://docs.site.com/auth/oauth-guide",
])
def test_public_pages_that_merely_mention_one(url):
    assert not is_auth_path(url)


def test_a_store_that_isnt_open_yet_is_a_login_wall():
    text = page(SHOPIFY_NOT_OPEN).get_text(" ", strip=True)
    assert looks_like_login_wall("https://shop.myshopify.com", text, page(SHOPIFY_NOT_OPEN))


# Shopify's current theme (Horizon): the password box sits in a dialog, and the
# form carries the hidden form_type marker. Trimmed from a live store.
SHOPIFY_HORIZON_NOT_OPEN = """
<main><h1>My Store 3</h1><p>Opening soon</p><p>Be the first to know when we launch.</p></main>
<footer><form action="/contact#contact_form"><input type="email" name="contact[email]"></form></footer>
<form method="post" action="/password" id="login_form" class="storefront-password-form">
  <input type="hidden" name="form_type" value="storefront_password" />
  <dialog-component id="password-form"><dialog class="password-dialog">
    <input type="password" name="password" id="Password">
  </dialog></dialog-component>
</form>
"""


def test_a_store_that_isnt_open_yet_in_any_theme_is_a_login_wall():
    # Even with plenty of text: the marker only appears on this page
    assert looks_like_login_wall("https://shop.myshopify.com", "Opening soon. " * 200, page(SHOPIFY_HORIZON_NOT_OPEN))


def test_the_served_page_counts_when_the_rendered_copy_lost_its_forms():
    rendered = page("<main><h1>My Store 3</h1><p>Opening soon</p></main>")
    assert looks_like_login_wall("https://shop.myshopify.com", "My Store 3 Opening soon", page(SHOPIFY_HORIZON_NOT_OPEN), rendered)


def test_a_real_page_with_a_login_box_in_its_header_is_kept():
    html = '<header><input type="PASSWORD"></header><main>' + "Real content. " * 100 + "</main>"
    text = "Real content. " * 100
    assert len(text) > MAX_TEXT_ON_A_LOGIN_PAGE
    assert not looks_like_login_wall("https://site.com", text, page(html))


@pytest.mark.parametrize("chrome", [
    "<header>{box}</header>",
    "<nav>{box}</nav>",
    "<dialog>{box}</dialog>",
    '<div hidden>{box}</div>',
    '<div aria-hidden="true">{box}</div>',
])
def test_a_short_page_with_the_sites_login_box_in_its_chrome_is_kept(chrome):
    # Shops and forums put a login dropdown on every page, short ones included
    box = '<form><input type="password"></form>'
    html = chrome.format(box=box) + "<main><h1>Contact</h1><p>Call us on 0123.</p></main>"
    assert not looks_like_login_wall("https://shop.com/contact", "Contact Call us on 0123.", page(html))


def test_a_short_page_without_a_password_box_is_not_a_login_wall():
    assert not looks_like_login_wall("https://site.com/contact", "Call us", page("<p>Call us</p>"))


def test_an_admin_url_is_a_login_wall_whatever_it_shows():
    assert looks_like_login_wall("https://shop.myshopify.com/admin", "Redirecting…", page("<p>Redirecting…</p>"))
