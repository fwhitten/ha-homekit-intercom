"""Sensors showing the last announcement for each zone."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeKitIntercomConfigEntry
from .entity import ZoneEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeKitIntercomConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add sensors for each zone."""
    for subentry_id, zone in entry.runtime_data.zones.items():
        async_add_entities(
            [LastAnnouncementSensor(zone), LastSentSensor(zone), PendingSensor(zone)],
            config_subentry_id=subentry_id,
        )


class _ZoneSensor(ZoneEntity, SensorEntity):
    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.zone.async_add_listener(self.async_write_ha_state))


class LastAnnouncementSensor(_ZoneSensor):
    """Text of the last email sent for the zone."""

    _attr_translation_key = "last_announcement"

    def __init__(self, zone) -> None:
        """Initialise the sensor."""
        super().__init__(zone, "last_announcement")

    @property
    def native_value(self) -> str | None:
        """Return the last announced text (truncated to fit a state)."""
        if self.zone.last_text is None:
            return None
        return self.zone.last_text[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return details of the last send."""
        return {
            "subject": self.zone.last_subject,
            "messages": self.zone.last_messages,
            "last_error": self.zone.last_error,
        }


class LastSentSensor(_ZoneSensor):
    """Time the zone last sent an email."""

    _attr_translation_key = "last_sent"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, zone) -> None:
        """Initialise the sensor."""
        super().__init__(zone, "last_sent")

    @property
    def native_value(self):
        """Return when the last email was sent."""
        return self.zone.last_sent


class PendingSensor(_ZoneSensor):
    """Number of messages waiting to be sent."""

    _attr_translation_key = "pending"

    def __init__(self, zone) -> None:
        """Initialise the sensor."""
        super().__init__(zone, "pending")

    @property
    def native_value(self) -> int:
        """Return the queue length."""
        return len(self.zone.pending)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the queued messages."""
        return {"messages": [a.message for a in self.zone.pending]}
