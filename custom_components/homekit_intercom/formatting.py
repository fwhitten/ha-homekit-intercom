"""Pure helpers for turning queued messages into announcement text."""

from __future__ import annotations

from collections.abc import Sequence

_END_PUNCTUATION = ".!?"
_STRIP_CHARS = " .!?,;:"


def clean_message(message: str) -> str:
    """Collapse whitespace and strip a message."""
    return " ".join(str(message).split())


def _first_word(text: str) -> str:
    return text.split(" ", 1)[0]


def _lower_first(text: str) -> str:
    """Lowercase a leading capital unless it looks like an acronym or "I"."""
    word = _first_word(text)
    if not word[:1].isupper() or word == "I" or word.startswith("I'"):
        return text
    if len(word) > 1 and word[1:] != word[1:].lower():
        return text  # e.g. "TV", "HomePod"
    return text[0].lower() + text[1:]


def _upper_first(text: str) -> str:
    """Capitalise a leading lowercase letter unless the word is mixed case."""
    word = _first_word(text)
    if word != word.lower():
        return text  # e.g. "iPhone"
    return text[0].upper() + text[1:]


def join_messages(messages: Sequence[str]) -> str:
    """Join messages as "a and b" / "a, b and c" into one sentence."""
    parts = [clean_message(m) for m in messages]
    parts = [p for p in parts if p.strip(_STRIP_CHARS)]
    if not parts:
        return ""

    ending = parts[-1][-1] if parts[-1][-1] in "!?" else "."
    body = [p.rstrip(_STRIP_CHARS) for p in parts]
    body = [body[0], *(_lower_first(p) for p in body[1:])]

    text = body[0] if len(body) == 1 else f"{', '.join(body[:-1])} and {body[-1]}"
    return _upper_first(text) + ending


def build_subject(prefix: str, text: str) -> str:
    """Build the email subject the Siri Shortcut looks for."""
    return f"{prefix}: {text}"


def split_into_batches(messages: Sequence[str], prefix: str, max_length: int) -> list[list[str]]:
    """Group messages so each joined subject stays within max_length.

    A single message that is too long on its own is still sent by itself.
    """
    batches: list[list[str]] = []
    current: list[str] = []
    for message in messages:
        candidate = [*current, message]
        if current and len(build_subject(prefix, join_messages(candidate))) > max_length:
            batches.append(current)
            current = [message]
        else:
            current = candidate
    if current:
        batches.append(current)
    return batches
