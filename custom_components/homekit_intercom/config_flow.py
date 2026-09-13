"""Config flow for HomeKit Intercom."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)

from .const import (
    CONF_BATCH_WINDOW,
    CONF_MAX_LENGTH,
    CONF_MAX_WAIT,
    CONF_NOTIFY_SERVICE,
    CONF_PREFIX,
    CONF_PRESENCE_ENTITY,
    CONF_QUIET_END,
    CONF_QUIET_HOURS,
    CONF_QUIET_MODE,
    CONF_QUIET_START,
    CONF_RECIPIENT,
    DEFAULT_OPTIONS,
    DOMAIN,
    PRESENCE_DOMAINS,
    QUIET_MODES,
    SUBENTRY_ZONE,
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_EXCLUDED_NOTIFY_SERVICES = {"send_message", "persistent_notification", "notify"}


def _notify_services(hass: HomeAssistant) -> list[str]:
    services = hass.services.async_services_for_domain(NOTIFY_DOMAIN)
    return sorted(name for name in services if name not in _EXCLUDED_NOTIFY_SERVICES)


def _delivery_schema(hass: HomeAssistant) -> dict[vol.Marker, Any]:
    return {
        vol.Required(CONF_NOTIFY_SERVICE): SelectSelector(
            SelectSelectorConfig(
                options=_notify_services(hass),
                custom_value=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(CONF_RECIPIENT): TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL)),
    }


def _validate_delivery(hass: HomeAssistant, user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    service = str(user_input[CONF_NOTIFY_SERVICE]).removeprefix(f"{NOTIFY_DOMAIN}.")
    user_input[CONF_NOTIFY_SERVICE] = service
    user_input[CONF_RECIPIENT] = str(user_input[CONF_RECIPIENT]).strip()
    if not hass.services.has_service(NOTIFY_DOMAIN, service):
        errors[CONF_NOTIFY_SERVICE] = "service_not_found"
    if not EMAIL_RE.match(user_input[CONF_RECIPIENT]):
        errors[CONF_RECIPIENT] = "invalid_email"
    return errors


ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): TextSelector(),
        vol.Required(CONF_PREFIX): TextSelector(),
        vol.Optional(CONF_PRESENCE_ENTITY): EntitySelector(
            EntitySelectorConfig(domain=PRESENCE_DOMAINS)
        ),
    }
)


def _normalise_zone(user_input: dict[str, Any]) -> dict[str, Any]:
    zone = {
        CONF_NAME: str(user_input[CONF_NAME]).strip(),
        CONF_PREFIX: str(user_input[CONF_PREFIX]).strip().rstrip(":").strip(),
    }
    if presence := user_input.get(CONF_PRESENCE_ENTITY):
        zone[CONF_PRESENCE_ENTITY] = presence
    return zone


class HomeKitIntercomConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the flow."""
        self._delivery: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return HomeKitIntercomOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Zones are added as subentries."""
        return {SUBENTRY_ZONE: ZoneSubentryFlow}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose how emails are sent."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (errors := _validate_delivery(self.hass, user_input)):
                self._delivery = user_input
                return await self.async_step_zone()
        schema = self.add_suggested_values_to_schema(
            vol.Schema(_delivery_schema(self.hass)), user_input or {}
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_zone(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Add the first zone."""
        if user_input is not None:
            zone = _normalise_zone(user_input)
            return self.async_create_entry(
                title="HomeKit Intercom",
                data={},
                options={**DEFAULT_OPTIONS, **self._delivery},
                subentries=[
                    ConfigSubentryData(
                        data=zone,
                        subentry_type=SUBENTRY_ZONE,
                        title=zone[CONF_NAME],
                        unique_id=None,
                    )
                ],
            )
        schema = self.add_suggested_values_to_schema(
            ZONE_SCHEMA, {CONF_NAME: "All HomePods", CONF_PREFIX: "HA Announce All"}
        )
        return self.async_show_form(step_id="zone", data_schema=schema)


class HomeKitIntercomOptionsFlow(OptionsFlow):
    """Change delivery, batching and quiet-hours settings."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (errors := _validate_delivery(self.hass, user_input)):
                return self.async_create_entry(data={**DEFAULT_OPTIONS, **user_input})

        seconds = NumberSelectorConfig(mode=NumberSelectorMode.BOX, unit_of_measurement="s")
        schema = vol.Schema(
            {
                **_delivery_schema(self.hass),
                vol.Required(CONF_BATCH_WINDOW): NumberSelector(
                    NumberSelectorConfig(**{**seconds, "min": 0, "max": 300, "step": 0.5})
                ),
                vol.Required(CONF_MAX_WAIT): NumberSelector(
                    NumberSelectorConfig(**{**seconds, "min": 1, "max": 3600, "step": 1})
                ),
                vol.Required(CONF_MAX_LENGTH): NumberSelector(
                    NumberSelectorConfig(min=50, max=2000, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_QUIET_HOURS): BooleanSelector(),
                vol.Required(CONF_QUIET_START): TimeSelector(),
                vol.Required(CONF_QUIET_END): TimeSelector(),
                vol.Required(CONF_QUIET_MODE): SelectSelector(
                    SelectSelectorConfig(options=QUIET_MODES, translation_key=CONF_QUIET_MODE)
                ),
            }
        )
        suggested = user_input or {**DEFAULT_OPTIONS, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
        )


class ZoneSubentryFlow(ConfigSubentryFlow):
    """Add or edit a HomePod zone."""

    def _name_taken(self, name: str, exclude: str | None = None) -> bool:
        return any(
            sub.subentry_id != exclude and sub.title.casefold() == name.casefold()
            for sub in self._get_entry().subentries.values()
            if sub.subentry_type == SUBENTRY_ZONE
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Add a zone."""
        errors: dict[str, str] = {}
        if user_input is not None:
            zone = _normalise_zone(user_input)
            if not zone[CONF_NAME] or not zone[CONF_PREFIX]:
                errors["base"] = "empty"
            elif self._name_taken(zone[CONF_NAME]):
                errors[CONF_NAME] = "name_exists"
            else:
                return self.async_create_entry(title=zone[CONF_NAME], data=zone)
        schema = self.add_suggested_values_to_schema(
            ZONE_SCHEMA,
            user_input or {CONF_NAME: "Kitchen HomePods", CONF_PREFIX: "HA Announce Kitchen"},
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a zone."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            zone = _normalise_zone(user_input)
            if not zone[CONF_NAME] or not zone[CONF_PREFIX]:
                errors["base"] = "empty"
            elif self._name_taken(zone[CONF_NAME], exclude=subentry.subentry_id):
                errors[CONF_NAME] = "name_exists"
            else:
                return self.async_update_and_abort(
                    self._get_entry(), subentry, title=zone[CONF_NAME], data=zone
                )
        schema = self.add_suggested_values_to_schema(ZONE_SCHEMA, user_input or dict(subentry.data))
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)
