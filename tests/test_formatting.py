"""Tests for message joining."""

from custom_components.homekit_intercom.formatting import (
    build_subject,
    join_messages,
    split_into_batches,
)


def test_single() -> None:
    assert join_messages(["The washing machine has finished"]) == (
        "The washing machine has finished."
    )
    assert join_messages(["Is the door locked?"]) == "Is the door locked?"


def test_two_and_three() -> None:
    assert join_messages(["The washing machine has finished.", "The front door is open."]) == (
        "The washing machine has finished and the front door is open."
    )
    assert join_messages(["Dishwasher done", "Dryer done", "Post has arrived!"]) == (
        "Dishwasher done, dryer done and post has arrived!"
    )


def test_case_heuristics() -> None:
    assert join_messages(["TV is on", "I left the oven on", "HomePod updated"]) == (
        "TV is on, I left the oven on and HomePod updated."
    )
    assert join_messages(["iPhone battery is low"]) == "iPhone battery is low."
    assert join_messages(["the gate is open"]) == "The gate is open."


def test_empty_and_whitespace() -> None:
    assert join_messages([]) == ""
    assert join_messages(["  ", "."]) == ""
    assert join_messages(["  Rain   is\n coming  "]) == "Rain is coming."


def test_subject() -> None:
    assert build_subject("HA Announce All", "The washing machine has finished.") == (
        "HA Announce All: The washing machine has finished."
    )


def test_split() -> None:
    messages = ["a" * 20, "b" * 20, "c" * 20]
    assert split_into_batches(messages, "P", 1000) == [messages]
    batches = split_into_batches(messages, "P", 50)
    assert batches == [["a" * 20, "b" * 20], ["c" * 20]]
    assert split_into_batches(["x" * 100], "P", 50) == [["x" * 100]]
