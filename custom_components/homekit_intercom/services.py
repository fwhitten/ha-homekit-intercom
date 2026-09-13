"""Actions for HomeKit Intercom."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, ENTITY_MATCH_ALL
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .announcer import Announcement
from .const import (
    ATTR_COOLDOWN,
    ATTR_IGNORE_QUIET_HOURS,
    ATTR_KEY,
    ATTR_MESSAGE,
    ATTR_PRIORITY,
    ATTR_QUIET_HOURS,
    ATTR_STALE_AFTER,
    DOMAIN,
    PRIORITIES,
    PRIORITY_NORMAL,
    QUIET_HOURS_CHOICES,
    QUIET_HOURS_IGNORE,
    SERVICE_ANNOUNCE,
    SERVICE_FLUSH,
)

if TYPE_CHECKING:
    from .announcer import ZoneAnnouncer

ANNOUNCE_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_PRIORITY, default=PRIORITY_NORMAL): vol.In(PRIORITIES),
        vol.Optional(ATTR_KEY): cv.string,
        vol.Optional(ATTR_COOLDOWN): cv.positive_time_period,
        vol.Optional(ATTR_QUIET_HOURS): vol.In(QUIET_HOURS_CHOICES),
        vol.Optional(ATTR_STALE_AFTER): cv.positive_time_period,
        vol.Optional(ATTR_IGNORE_QUIET_HOURS, default=False): cv.boolean,
    }
)
FLUSH_SCHEMA = cv.make_entity_service_schema({})


async def _async_get_zones(call: ServiceCall) -> list[ZoneAnnouncer]:
    """Resolve targeted entities to zones."""
    hass = call.hass
    registry = er.async_get(hass)
    zones: dict[str, ZoneAnnouncer] = {}
    entity_ids = call.data.get(ATTR_ENTITY_ID, [])
    device_ids = call.data.get(ATTR_DEVICE_ID, [])
    if entity_ids == ENTITY_MATCH_ALL:
        return [
            zone
            for config_entry in hass.config_entries.async_loaded_entries(DOMAIN)
            for zone in config_entry.runtime_data.zones.values()
        ]
    reg_entries = [
        reg_entry
        for entity_id in (entity_ids if isinstance(entity_ids, list) else [])
        if (reg_entry := registry.async_get(entity_id)) is not None
    ]
    for device_id in device_ids if isinstance(device_ids, list) else []:
        reg_entries.extend(er.async_entries_for_device(registry, device_id))
    for reg_entry in reg_entries:
        if reg_entry.platform != DOMAIN:
            continue
        config_entry = hass.config_entries.async_get_entry(reg_entry.config_entry_id or "")
        if config_entry is None or getattr(config_entry, "runtime_data", None) is None:
            continue
        zone = config_entry.runtime_data.zones.get(reg_entry.config_subentry_id or "")
        if zone is not None:
            zones[f"{config_entry.entry_id}_{zone.zone_id}"] = zone
    if not zones:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_zones_targeted")
    return list(zones.values())


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the announce and flush actions."""

    async def async_announce(call: ServiceCall) -> None:
        if ATTR_QUIET_HOURS in call.data:
            ignore_quiet_hours = call.data[ATTR_QUIET_HOURS] == QUIET_HOURS_IGNORE
        else:
            ignore_quiet_hours = call.data[ATTR_IGNORE_QUIET_HOURS]
        for zone in await _async_get_zones(call):
            await zone.async_announce(
                Announcement(
                    message=call.data[ATTR_MESSAGE],
                    priority=call.data[ATTR_PRIORITY],
                    key=call.data.get(ATTR_KEY),
                    ignore_quiet_hours=ignore_quiet_hours,
                    stale_after=call.data.get(ATTR_STALE_AFTER),
                ),
                cooldown=call.data.get(ATTR_COOLDOWN),
            )

    async def async_flush(call: ServiceCall) -> None:
        for zone in await _async_get_zones(call):
            await zone.async_flush()

    hass.services.async_register(DOMAIN, SERVICE_ANNOUNCE, async_announce, ANNOUNCE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_FLUSH, async_flush, FLUSH_SCHEMA)
