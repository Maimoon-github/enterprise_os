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

The stored record of the choices a message actually went out with — what the
inbox shows under it, and what a later tap on one of them is read against.
Encrypted: the choices can echo what the customer said.
"""

from typing import Optional

from app.channels.base import InteractiveMessage
from app.channels.interactive import all_choices, choice_text
from app.core.encryption import decrypt_json, encrypt_json

# chat_history.attributes key the record is stored under
SENT_CHOICES_ATTRIBUTE = "interactive_sent"


def encode_sent_choices(message: InteractiveMessage, as_text: bool, numbered: bool = False) -> dict:
    """The record for one sent message; `as_text` when the choices had to go
    as a numbered list instead of buttons; `numbered` when the customer saw
    them numbered either way (so a bare "2" picks the second)."""
    return encrypt_json({
        "kind": message.kind.value,
        "as_text": as_text,
        "numbered": as_text or numbered,
        "choices": [{"id": c.id, "text": choice_text(c)} for c in all_choices(message)],
    })


def decode_sent_choices(value) -> Optional[dict]:
    record = decrypt_json(value)
    return record if isinstance(record, dict) else None


def sent_numbered_choice(record: Optional[dict], typed: str) -> Optional[str]:
    """The full text of the choice the customer typed the number of (1-based),
    when the record's choices were shown numbered. A number that is itself
    one of the choices ("2" guests) is that choice, not a position."""
    choices = (record or {}).get("choices") or []
    if not (record or {}).get("numbered") or not typed.isdecimal():
        return None
    if any((choice.get("text") or "").strip() == typed for choice in choices):
        return None
    number = int(typed)
    return choices[number - 1].get("text") if 1 <= number <= len(choices) else None


def sent_choice_text(record: Optional[dict], choice_id: str) -> Optional[str]:
    """The full text of the choice with this id in a sent-choices record."""
    for choice in (record or {}).get("choices") or []:
        if choice.get("id") == choice_id:
            return choice.get("text")
    return None
