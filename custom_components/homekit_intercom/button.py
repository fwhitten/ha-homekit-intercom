"""Test button for each intercom zone."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeKitIntercomConfigEntry
from .announcer import Announcement
from .const import PRIORITY_URGENT
from .entity import ZoneEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeKitIntercomConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a test button for each zone."""
    for subentry_id, zone in entry.runtime_data.zones.items():
        async_add_entities([TestAnnouncementButton(zone)], config_subentry_id=subentry_id)


class TestAnnouncementButton(ZoneEntity, ButtonEntity):
    """Immediately send a test announcement."""

    _attr_translation_key = "test"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, zone) -> None:
        """Initialise the button."""
        super().__init__(zone, "test")

    async def async_press(self) -> None:
        """Send the test announcement."""
        await self.zone.async_announce(
            Announcement(
                message=f"This is a test announcement for {self.zone.name}",
                priority=PRIORITY_URGENT,
            )
        )
