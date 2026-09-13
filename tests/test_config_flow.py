"""Tests for the config flow."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.homekit_intercom.const import DOMAIN, SUBENTRY_ZONE

from .conftest import setup_entry


async def test_user_flow(hass: HomeAssistant, notify_calls) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"notify_service": "notify.missing", "recipient": "nope"}
    )
    assert result["errors"] == {
        "notify_service": "service_not_found",
        "recipient": "invalid_email",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"notify_service": "notify.gmail", "recipient": "me@example.com"}
    )
    assert result["step_id"] == "zone"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "All HomePods", "prefix": "HA Announce All:"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.options["notify_service"] == "gmail"
    (zone,) = entry.subentries.values()
    assert zone.data == {"name": "All HomePods", "prefix": "HA Announce All"}
    await hass.async_block_till_done()
    assert hass.states.get("notify.all_homepods") is not None


async def test_add_and_edit_zone(hass: HomeAssistant, notify_calls) -> None:
    entry = await setup_entry(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ZONE), context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "kitchen homepods", "prefix": "X"}
    )
    assert result["errors"] == {"name": "name_exists"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Bedroom",
            "prefix": "HA Announce Bedroom",
            "presence_entity": "binary_sensor.bedroom_occupancy",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("notify.bedroom") is not None
    bedroom = next(z for z in entry.runtime_data.zones.values() if z.name == "Bedroom")
    assert bedroom.presence_entity == "binary_sensor.bedroom_occupancy"

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ZONE),
        context={"source": config_entries.SOURCE_RECONFIGURE, "subentry_id": "kitchen"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Kitchen HomePods", "prefix": "HA Announce Cooking"}
    )
    assert result["type"] is FlowResultType.ABORT
    await hass.async_block_till_done()
    assert entry.runtime_data.zones["kitchen"].prefix == "HA Announce Cooking"


async def test_options_flow(hass: HomeAssistant, notify_calls) -> None:
    entry = await setup_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "notify_service": "gmail",
            "recipient": "me@example.com",
            "batch_window": 10,
            "max_wait": 60,
            "max_length": 300,
            "quiet_hours": True,
            "quiet_start": "23:00:00",
            "quiet_end": "06:30:00",
            "quiet_mode": "drop",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.runtime_data.batch_window.total_seconds() == 10
    assert entry.runtime_data.quiet_mode == "drop"
