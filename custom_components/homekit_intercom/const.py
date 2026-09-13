"""Constants for HomeKit Intercom."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "homekit_intercom"

SUBENTRY_ZONE: Final = "zone"

# Config entry options
CONF_NOTIFY_SERVICE: Final = "notify_service"
CONF_RECIPIENT: Final = "recipient"
CONF_BATCH_WINDOW: Final = "batch_window"
CONF_MAX_WAIT: Final = "max_wait"
CONF_MAX_LENGTH: Final = "max_length"
CONF_QUIET_HOURS: Final = "quiet_hours"
CONF_QUIET_START: Final = "quiet_start"
CONF_QUIET_END: Final = "quiet_end"
CONF_QUIET_MODE: Final = "quiet_mode"

# Zone subentry data
CONF_PREFIX: Final = "prefix"
CONF_PRESENCE_ENTITY: Final = "presence_entity"

PRESENCE_DOMAINS: Final = [
    "binary_sensor",
    "device_tracker",
    "group",
    "input_boolean",
    "person",
    "zone",
]

# Service fields
ATTR_MESSAGE: Final = "message"
ATTR_PRIORITY: Final = "priority"
ATTR_KEY: Final = "key"
ATTR_COOLDOWN: Final = "cooldown"
ATTR_IGNORE_QUIET_HOURS: Final = "ignore_quiet_hours"  # legacy, kept for existing YAML
ATTR_QUIET_HOURS: Final = "quiet_hours"
ATTR_STALE_AFTER: Final = "stale_after"

QUIET_HOURS_RESPECT: Final = "respect"
QUIET_HOURS_IGNORE: Final = "ignore"
QUIET_HOURS_CHOICES: Final = [QUIET_HOURS_RESPECT, QUIET_HOURS_IGNORE]

SERVICE_ANNOUNCE: Final = "announce"
SERVICE_FLUSH: Final = "flush"

PRIORITY_NORMAL: Final = "normal"
PRIORITY_URGENT: Final = "urgent"
PRIORITIES: Final = [PRIORITY_NORMAL, PRIORITY_URGENT]

QUIET_MODE_HOLD: Final = "hold"
QUIET_MODE_DROP: Final = "drop"
QUIET_MODES: Final = [QUIET_MODE_HOLD, QUIET_MODE_DROP]

EVENT_ANNOUNCED: Final = "homekit_intercom_announced"
EVENT_DISCARDED: Final = "homekit_intercom_discarded"

HOLD_QUIET_HOURS: Final = "quiet_hours"
HOLD_PRESENCE: Final = "presence"

DEFAULT_BATCH_WINDOW: Final = 5
DEFAULT_MAX_WAIT: Final = 30
DEFAULT_MAX_LENGTH: Final = 250
DEFAULT_QUIET_START: Final = "22:00:00"
DEFAULT_QUIET_END: Final = "07:00:00"

DEFAULT_OPTIONS: Final = {
    CONF_BATCH_WINDOW: DEFAULT_BATCH_WINDOW,
    CONF_MAX_WAIT: DEFAULT_MAX_WAIT,
    CONF_MAX_LENGTH: DEFAULT_MAX_LENGTH,
    CONF_QUIET_HOURS: False,
    CONF_QUIET_START: DEFAULT_QUIET_START,
    CONF_QUIET_END: DEFAULT_QUIET_END,
    CONF_QUIET_MODE: QUIET_MODE_HOLD,
}
