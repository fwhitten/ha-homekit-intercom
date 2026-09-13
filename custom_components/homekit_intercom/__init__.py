"""HomeKit Intercom: send batched announcement emails for Siri Shortcuts."""

from __future__ import annotations

import logging
from pathlib import Path
import shutil

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .announcer import IntercomManager
from .const import DOMAIN
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.NOTIFY, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type HomeKitIntercomConfigEntry = ConfigEntry[IntercomManager]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register actions."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HomeKitIntercomConfigEntry) -> bool:
    """Set up HomeKit Intercom from a config entry."""
    entry.runtime_data = IntercomManager(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.runtime_data.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.async_add_executor_job(_install_blueprints, Path(hass.config.path("blueprints")))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HomeKitIntercomConfigEntry) -> bool:
    """Unload a config entry, sending anything already queued."""
    await entry.runtime_data.async_shutdown()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: HomeKitIntercomConfigEntry) -> None:
    """Reload when options or zones change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _install_blueprints(blueprint_root: Path) -> None:
    """Copy bundled blueprints into the user's config, keeping them up to date."""
    source_root = Path(__file__).parent / "blueprints"
    for source in source_root.glob("*/*.yaml"):
        target = blueprint_root / source.parent.name / DOMAIN / source.name
        if target.exists() and target.read_bytes() == source.read_bytes():
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        except OSError as err:
            _LOGGER.warning("Could not install blueprint %s: %s", source.name, err)
