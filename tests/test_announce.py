"""Tests for batching and delivery."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from custom_components.homekit_intercom.const import DOMAIN, EVENT_ANNOUNCED

from .conftest import setup_entry

ALL = "notify.all_homepods"
KITCHEN = "notify.kitchen_homepods"


async def _announce(hass: HomeAssistant, target: str, message: str, **data) -> None:
    await hass.services.async_call(
        DOMAIN,
        "announce",
        {"entity_id": target, "message": message, **data},
        blocking=True,
    )


async def _advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_entities_created(hass: HomeAssistant, notify_calls) -> None:
    await setup_entry(hass)
    for entity_id in (
        ALL,
        KITCHEN,
        "sensor.all_homepods_last_announcement",
        "sensor.kitchen_homepods_pending_messages",
        "button.kitchen_homepods_send_test_announcement",
    ):
        assert hass.states.get(entity_id) is not None, entity_id


async def test_batches_close_messages(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, notify_calls: list[ServiceCall]
) -> None:
    await setup_entry(hass)
    events = []
    hass.bus.async_listen(EVENT_ANNOUNCED, events.append)

    await _announce(hass, ALL, "The washing machine has finished.")
    await _advance(hass, freezer, 3)
    await _announce(hass, ALL, "The front door is open")
    await _advance(hass, freezer, 3)
    await _announce(hass, ALL, "Dinner is ready")
    await _advance(hass, freezer, 3)
    assert notify_calls == []
    assert hass.states.get("sensor.all_homepods_pending_messages").state == "3"

    await _advance(hass, freezer, 3)
    assert len(notify_calls) == 1
    assert notify_calls[0].data == {
        "title": "HA Announce All: The washing machine has finished, the front door is open and dinner is ready.",
        "message": "The washing machine has finished, the front door is open and dinner is ready.",
        "target": ["me@example.com"],
    }
    assert len(events) == 1
    state = hass.states.get("sensor.all_homepods_last_announcement")
    assert state.state.startswith("The washing machine")
    assert hass.states.get("sensor.all_homepods_pending_messages").state == "0"


async def test_zones_are_separate(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, notify_calls
) -> None:
    await setup_entry(hass)
    await _announce(hass, ALL, "One")
    await _announce(hass, KITCHEN, "Two")
    await _advance(hass, freezer, 6)
    assert sorted(c.data["title"] for c in notify_calls) == [
        "HA Announce All: One.",
        "HA Announce Kitchen: Two.",
    ]


async def test_multiple_targets(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, notify_calls
) -> None:
    await setup_entry(hass)
    await _announce(hass, f"{ALL},{KITCHEN}", "Hello")
    await _advance(hass, freezer, 6)
    assert len(notify_calls) == 2


async def test_max_wait(hass: HomeAssistant, freezer: FrozenDateTimeFactory, notify_calls) -> None:
    await setup_entry(hass, batch_window=5, max_wait=12)
    for i in range(4):
        await _announce(hass, ALL, f"Message {i}")
        await _advance(hass, freezer, 4)
    # 16s elapsed but max_wait of 12s must have triggered a send.
    assert len(notify_calls) == 1
    assert "Message 0" in notify_calls[0].data["title"]


async def test_urgent_sends_immediately_with_queue(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, notify_calls
) -> None:
    await setup_entry(hass)
    await _announce(hass, ALL, "Washing done")
    await _announce(hass, ALL, "Smoke detected", priority="urgent")
    assert len(notify_calls) == 1
    assert notify_calls[0].data["title"] == "HA Announce All: Washing done and smoke detected."
    await _advance(hass, freezer, 10)
    assert len(notify_calls) == 1


async def test_duplicates_and_keys(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, notify_calls
) -> None:
    await setup_entry(hass)
    await _announce(hass, ALL, "Door open")
    await _announce(hass, ALL, "door open")
    await _announce(hass, ALL, "Temperature is 20 degrees", key="temp")
    await _announce(hass, ALL, "Temperature is 21 degrees", key="temp")
    await _advance(hass, freezer, 6)
    assert notify_calls[0].data["title"] == (
        "HA Announce All: Door open and temperature is 21 degrees."
    )


async def test_cooldown(hass: HomeAssistant, freezer: FrozenDateTimeFactory, notify_calls) -> None:
    await setup_entry(hass)
    cooldown = {"key": "washer", "cooldown": {"minutes": 10}}
    await _announce(hass, ALL, "Washer done", **cooldown)
    await _advance(hass, freezer, 6)
    await _announce(hass, ALL, "Washer done", **cooldown)
    await _advance(hass, freezer, 6)
    assert len(notify_calls) == 1
    await _advance(hass, freezer, 600)
    await _announce(hass, ALL, "Washer done", **cooldown)
    await _advance(hass, freezer, 6)
    assert len(notify_calls) == 2


async def test_quiet_hours_hold(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, notify_calls
) -> None:
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2026-09-13 23:00:00+00:00")
    await setup_entry(hass, quiet_hours=True, quiet_start="22:00:00", quiet_end="07:00:00")

    await _announce(hass, ALL, "Bins go out tomorrow")
    await _announce(hass, KITCHEN, "Late but important", ignore_quiet_hours=True)
    await _advance(hass, freezer, 6)
    assert [c.data["title"] for c in notify_calls] == ["HA Announce Kitchen: Late but important."]

    freezer.move_to("2026-09-14 07:00:01+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert notify_calls[-1].data["title"] == "HA Announce All: Bins go out tomorrow."


async def test_quiet_hours_drop(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, notify_calls
) -> None:
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2026-09-13 23:00:00+00:00")
    await setup_entry(
        hass, quiet_hours=True, quiet_start="22:00:00", quiet_end="07:00:00", quiet_mode="drop"
    )
    await _announce(hass, ALL, "Dropped")
    await _announce(hass, KITCHEN, "Fire", priority="urgent")
    freezer.move_to("2026-09-14 08:00:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert [c.data["title"] for c in notify_calls] == ["HA Announce Kitchen: Fire."]


async def test_split_long(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, notify_calls
) -> None:
    await setup_entry(hass, max_length=60)
    await _announce(hass, ALL, "The washing machine has finished")
    await _announce(hass, ALL, "The front door has been left open")
    await _advance(hass, freezer, 6)
    assert len(notify_calls) == 2


async def test_notify_entity_and_flush(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, notify_calls
) -> None:
    await setup_entry(hass)
    await hass.services.async_call(
        "notify", "send_message", {"entity_id": KITCHEN, "message": "Kettle boiled"}, blocking=True
    )
    assert notify_calls == []
    await hass.services.async_call(DOMAIN, "flush", {"entity_id": KITCHEN}, blocking=True)
    assert notify_calls[0].data["title"] == "HA Announce Kitchen: Kettle boiled."


async def test_test_button(hass: HomeAssistant, notify_calls) -> None:
    await setup_entry(hass)
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.all_homepods_send_test_announcement"},
        blocking=True,
    )
    assert notify_calls[0].data["title"] == (
        "HA Announce All: This is a test announcement for All HomePods."
    )


async def test_invalid_target(hass: HomeAssistant, notify_calls) -> None:
    await setup_entry(hass)
    with pytest.raises(ServiceValidationError):
        await _announce(hass, "sensor.all_homepods_pending_messages_missing", "Hi")


async def test_send_failure_is_recorded(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    await setup_entry(hass)  # notify.gmail not registered
    await _announce(hass, ALL, "Nobody hears this", priority="urgent")
    state = hass.states.get("sensor.all_homepods_last_announcement")
    assert state.attributes["last_error"]


async def test_unload_flushes(hass: HomeAssistant, notify_calls) -> None:
    entry = await setup_entry(hass)
    await _announce(hass, ALL, "Before reload")
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert notify_calls[0].data["title"] == "HA Announce All: Before reload."


async def test_blueprint_automation(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, notify_calls
) -> None:
    from homeassistant.setup import async_setup_component

    await setup_entry(hass)
    hass.states.async_set("binary_sensor.washer", "on", {"friendly_name": "Washing machine"})
    hass.states.async_set("binary_sensor.dryer", "on", {"friendly_name": "Dryer"})
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "alias": "Laundry",
                "use_blueprint": {
                    "path": "homekit_intercom/announce_on_state.yaml",
                    "input": {
                        "trigger_entity": ["binary_sensor.washer", "binary_sensor.dryer"],
                        "to_state": "off",
                        "zone": [KITCHEN],
                        "message": "The {{ state_attr(trigger.entity_id, 'friendly_name') | lower }} has finished",
                        "cooldown": {"minutes": 5},
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.washer", "off", {"friendly_name": "Washing machine"})
    await _advance(hass, freezer, 1)
    hass.states.async_set("binary_sensor.dryer", "off", {"friendly_name": "Dryer"})
    await _advance(hass, freezer, 6)
    assert [c.data["title"] for c in notify_calls] == [
        "HA Announce Kitchen: The washing machine has finished and the dryer has finished."
    ]

    # Same entity again within the cooldown is suppressed.
    hass.states.async_set("binary_sensor.washer", "on", {"friendly_name": "Washing machine"})
    hass.states.async_set("binary_sensor.washer", "off", {"friendly_name": "Washing machine"})
    await _advance(hass, freezer, 6)
    assert len(notify_calls) == 1
