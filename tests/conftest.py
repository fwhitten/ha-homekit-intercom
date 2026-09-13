"""Fixtures for HomeKit Intercom tests."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.homekit_intercom.const import (
    CONF_NOTIFY_SERVICE,
    CONF_PREFIX,
    CONF_RECIPIENT,
    DEFAULT_OPTIONS,
    DOMAIN,
    SUBENTRY_ZONE,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    return


@pytest.fixture
def notify_calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Mock the Google Mail notify action."""
    return async_mock_service(hass, "notify", "gmail")


def make_entry(**options) -> MockConfigEntry:
    """Build a config entry with All and Kitchen zones."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="HomeKit Intercom",
        data={},
        options={
            **DEFAULT_OPTIONS,
            CONF_NOTIFY_SERVICE: "gmail",
            CONF_RECIPIENT: "me@example.com",
            **options,
        },
        subentries_data=[
            {
                "data": {"name": "All HomePods", CONF_PREFIX: "HA Announce All"},
                "subentry_type": SUBENTRY_ZONE,
                "title": "All HomePods",
                "unique_id": None,
                "subentry_id": "all",
            },
            {
                "data": {"name": "Kitchen HomePods", CONF_PREFIX: "HA Announce Kitchen"},
                "subentry_type": SUBENTRY_ZONE,
                "title": "Kitchen HomePods",
                "unique_id": None,
                "subentry_id": "kitchen",
            },
        ],
    )


async def setup_entry(hass: HomeAssistant, **options) -> MockConfigEntry:
    """Add and set up an entry."""
    entry = make_entry(**options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
