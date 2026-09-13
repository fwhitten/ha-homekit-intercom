"""Notify entities: one per intercom zone."""

from __future__ import annotations

from homeassistant.components.notify import NotifyEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeKitIntercomConfigEntry
from .announcer import Announcement
from .entity import ZoneEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeKitIntercomConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a notify entity for each zone."""
    for subentry_id, zone in entry.runtime_data.zones.items():
        async_add_entities([ZoneNotifyEntity(zone)], config_subentry_id=subentry_id)


class ZoneNotifyEntity(ZoneEntity, NotifyEntity):
    """Announce on a zone's HomePods via notify.send_message."""

    _attr_name = None

    def __init__(self, zone) -> None:
        """Initialise the entity."""
        super().__init__(zone, "notify")

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Queue a normal-priority announcement."""
        await self.zone.async_announce(Announcement(message=message))
