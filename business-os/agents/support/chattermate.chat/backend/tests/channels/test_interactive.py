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

from app.channels.base import (
    InteractiveButton, InteractiveKind, InteractiveMessage, InteractiveRow,
    InteractiveSection,
)
from app.channels.interactive import from_options, to_text_fallback, truncate, validate_interactive
from app.channels.interactive_limits import WHATSAPP_LIMITS
from app.channels.sent_choices import decode_sent_choices, encode_sent_choices, sent_choice_text


class TestFromOptions:
    def test_few_short_options_become_buttons(self):
        message = from_options("Confirm the booking?", ["Yes", "No"])
        assert message.kind == InteractiveKind.BUTTONS
        assert [(b.id, b.title) for b in message.buttons] == [("qr_0", "Yes"), ("qr_1", "No")]
        assert validate_interactive(message) == []

    def test_more_than_three_options_become_a_list(self):
        options = [f"Option {i}" for i in range(WHATSAPP_LIMITS.max_buttons + 1)]
        message = from_options("Pick one", options)
        assert message.kind == InteractiveKind.LIST
        assert [r.title for r in message.sections[0].rows] == options
        assert validate_interactive(message) == []

    def test_one_long_option_switches_to_a_list_with_the_full_text(self):
        long_option = "Reschedule to next Saturday morning"
        message = from_options("What now?", ["Cancel", long_option])
        assert message.kind == InteractiveKind.LIST
        row = message.sections[0].rows[1]
        assert len(row.title) <= WHATSAPP_LIMITS.row_title_max and row.title.endswith("…")
        assert row.description == long_option
        assert validate_interactive(message) == []

    def test_options_beyond_the_list_cap_are_dropped(self):
        message = from_options("Pick", [str(i) for i in range(WHATSAPP_LIMITS.max_list_rows + 5)])
        assert len(message.sections[0].rows) == WHATSAPP_LIMITS.max_list_rows


class TestValidation:
    def test_buttons_limits(self):
        message = InteractiveMessage(
            kind=InteractiveKind.BUTTONS, body="x",
            buttons=[InteractiveButton(id="a", title="t" * (WHATSAPP_LIMITS.button_title_max + 1)),
                     InteractiveButton(id="a", title="ok")] * 2)
        errors = validate_interactive(message)
        assert any("1-3 buttons" in e for e in errors)
        assert any("button title" in e for e in errors)
        assert any("unique" in e for e in errors)

    def test_body_is_required(self):
        message = InteractiveMessage(kind=InteractiveKind.BUTTONS, body=" ",
                                     buttons=[InteractiveButton(id="a", title="A")])
        assert "body is required" in validate_interactive(message)

    def test_list_needs_label_and_titled_sections_when_several(self):
        message = InteractiveMessage(
            kind=InteractiveKind.LIST, body="x",
            sections=[InteractiveSection(rows=[InteractiveRow(id="1", title="a")]),
                      InteractiveSection(rows=[InteractiveRow(id="2", title="b")])])
        errors = validate_interactive(message)
        assert "list button label is required" in errors
        assert any("section titles are required" in e for e in errors)

    def test_list_row_cap_counts_across_sections(self):
        rows = [InteractiveRow(id=str(i), title=str(i)) for i in range(WHATSAPP_LIMITS.max_list_rows)]
        message = InteractiveMessage(
            kind=InteractiveKind.LIST, body="x", list_button_label="Pick",
            sections=[InteractiveSection(title="A", rows=rows),
                      InteractiveSection(title="B", rows=[InteractiveRow(id="x", title="x")])])
        assert any("rows in total" in e for e in validate_interactive(message))

    def test_cta_url_must_be_https(self):
        message = InteractiveMessage(kind=InteractiveKind.CTA_URL, body="x",
                                     display_text="Open", url="http://example.com")
        assert any("https" in e for e in validate_interactive(message))
        message.url = "https://example.com"
        assert validate_interactive(message) == []


class TestTextFallback:
    def test_numbered_choices_after_the_body(self):
        text = to_text_fallback(from_options("Confirm?", ["Yes", "No"]))
        assert text == "Confirm?\n\n1. Yes\n2. No"

    def test_cut_titles_fall_back_to_the_full_option(self):
        long_option = "Reschedule to next Saturday morning"
        text = to_text_fallback(from_options("What now?", ["Cancel", long_option]))
        assert text.endswith(f"2. {long_option}")

    def test_cta_shows_the_link(self):
        message = InteractiveMessage(kind=InteractiveKind.CTA_URL, body="Invoice ready",
                                     display_text="Pay", url="https://pay.example/1")
        assert to_text_fallback(message) == "Invoice ready\nPay: https://pay.example/1"


class TestTextFallbackLimits:
    def test_a_long_body_is_shortened_never_the_choices(self):
        text = to_text_fallback(from_options("x" * 5000, ["Yes", "No"]), max_length=4096)
        assert len(text) <= 4096
        assert text.endswith("1. Yes\n2. No")
        assert "…" in text

    def test_no_limit_keeps_everything(self):
        assert to_text_fallback(from_options("x" * 5000, ["Yes"])).startswith("x" * 5000)

    def test_a_real_row_description_is_shown(self):
        message = InteractiveMessage(
            kind=InteractiveKind.LIST, body="Pick", list_button_label="Pick",
            sections=[InteractiveSection(rows=[InteractiveRow(id="s1", title="U12", description="09:00")])])
        assert to_text_fallback(message).endswith("1. U12 — 09:00")


class TestSentChoicesRecord:
    def test_record_round_trips_encrypted_with_full_texts(self):
        long_option = "Reschedule to next Saturday morning"
        record = encode_sent_choices(from_options("What now?", ["Cancel", long_option]), as_text=False)

        assert long_option not in str(record)  # encrypted at rest
        decoded = decode_sent_choices(record)
        assert decoded["kind"] == "list" and decoded["as_text"] is False
        assert sent_choice_text(decoded, "qr_1") == long_option
        assert sent_choice_text(decoded, "qr_9") is None

    def test_unreadable_records_are_ignored(self):
        assert decode_sent_choices(None) is None
        assert decode_sent_choices("garbage") is None
        assert sent_choice_text(None, "qr_0") is None


def test_truncate_marks_the_cut():
    assert truncate("short", 10) == "short"
    assert truncate("a" * 30, 10) == "a" * 9 + "…"
