"""Base entity for HomeKit Intercom zones."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .announcer import ZoneAnnouncer
from .const import DOMAIN


class ZoneEntity(Entity):
    """An entity belonging to an intercom zone."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, zone: ZoneAnnouncer, key: str) -> None:
        """Initialise the entity."""
        self.zone = zone
        self._attr_unique_id = f"{zone.zone_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, zone.zone_id)},
            name=zone.name,
            manufacturer="HomeKit Intercom",
            model=f"{zone.prefix}:",
            entry_type=DeviceEntryType.SERVICE,
        )
