"""Batching, quiet hours, cooldown and delivery of announcements."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BATCH_WINDOW,
    CONF_MAX_LENGTH,
    CONF_MAX_WAIT,
    CONF_NOTIFY_SERVICE,
    CONF_PREFIX,
    CONF_QUIET_END,
    CONF_QUIET_HOURS,
    CONF_QUIET_MODE,
    CONF_QUIET_START,
    CONF_RECIPIENT,
    DEFAULT_OPTIONS,
    EVENT_ANNOUNCED,
    PRIORITY_NORMAL,
    PRIORITY_URGENT,
    QUIET_MODE_DROP,
    SUBENTRY_ZONE,
)
from .formatting import build_subject, clean_message, join_messages, split_into_batches

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class Announcement:
    """A single queued announcement."""

    message: str
    priority: str = PRIORITY_NORMAL
    key: str | None = None
    ignore_quiet_hours: bool = False
    queued_at: datetime = field(default_factory=dt_util.utcnow)

    @property
    def urgent(self) -> bool:
        """Return True if this announcement bypasses batching and quiet hours."""
        return self.priority == PRIORITY_URGENT


class IntercomManager:
    """Holds settings and zone announcers for one config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise from a config entry."""
        self.hass = hass
        self.entry = entry
        self.options: dict[str, Any] = {**DEFAULT_OPTIONS, **entry.options}
        self.zones: dict[str, ZoneAnnouncer] = {
            subentry_id: ZoneAnnouncer(
                self, subentry_id, subentry.data[CONF_NAME], subentry.data[CONF_PREFIX]
            )
            for subentry_id, subentry in entry.subentries.items()
            if subentry.subentry_type == SUBENTRY_ZONE
        }

    @property
    def notify_service(self) -> str:
        """Notify service name (without the notify. domain)."""
        return str(self.options[CONF_NOTIFY_SERVICE]).removeprefix(f"{NOTIFY_DOMAIN}.")

    @property
    def recipient(self) -> str:
        """Email address the Siri Shortcut watches."""
        return self.options[CONF_RECIPIENT]

    @property
    def batch_window(self) -> timedelta:
        """Quiet period after the last message before sending."""
        return timedelta(seconds=float(self.options[CONF_BATCH_WINDOW]))

    @property
    def max_wait(self) -> timedelta:
        """Longest a message may wait for the batch to close."""
        return timedelta(seconds=float(self.options[CONF_MAX_WAIT]))

    @property
    def max_length(self) -> int:
        """Maximum subject length before splitting into multiple emails."""
        return int(self.options[CONF_MAX_LENGTH])

    @property
    def quiet_mode(self) -> str:
        """Whether quiet-hours messages are held or dropped."""
        return self.options[CONF_QUIET_MODE]

    def _quiet_times(self) -> tuple[time, time] | None:
        if not self.options[CONF_QUIET_HOURS]:
            return None
        start = dt_util.parse_time(str(self.options[CONF_QUIET_START]))
        end = dt_util.parse_time(str(self.options[CONF_QUIET_END]))
        if start is None or end is None or start == end:
            return None
        return start, end

    def in_quiet_hours(self, now: datetime) -> bool:
        """Return True if now (UTC) falls within quiet hours."""
        if (times := self._quiet_times()) is None:
            return False
        start, end = times
        current = dt_util.as_local(now).time()
        if start < end:
            return start <= current < end
        return current >= start or current < end

    def quiet_hours_end(self, now: datetime) -> datetime:
        """Return the next end of quiet hours after now, in UTC."""
        _, end = self._quiet_times() or (None, time())
        local = dt_util.as_local(now)
        candidate = local.replace(
            hour=end.hour, minute=end.minute, second=end.second, microsecond=0
        )
        if candidate <= local:
            candidate += timedelta(days=1)
        return dt_util.as_utc(candidate)

    async def async_shutdown(self) -> None:
        """Send anything that is ready and cancel timers."""
        for zone in self.zones.values():
            await zone.async_flush()
            zone.cancel_timer()


class ZoneAnnouncer:
    """Collects announcements for one zone and sends them as a single email."""

    def __init__(self, manager: IntercomManager, zone_id: str, name: str, prefix: str) -> None:
        """Initialise the zone."""
        self.manager = manager
        self.hass = manager.hass
        self.zone_id = zone_id
        self.name = name
        self.prefix = prefix
        self.pending: list[Announcement] = []
        self.last_subject: str | None = None
        self.last_text: str | None = None
        self.last_messages: list[str] = []
        self.last_sent: datetime | None = None
        self.last_error: str | None = None
        self._cooldowns: dict[str, datetime] = {}
        self._batch_started: datetime | None = None
        self._unsub_timer: CALLBACK_TYPE | None = None
        self._listeners: list[Callable[[], None]] = []

    @callback
    def async_add_listener(self, update_callback: Callable[[], None]) -> CALLBACK_TYPE:
        """Register a callback for state changes; returns an unsubscribe function."""
        self._listeners.append(update_callback)
        return lambda: self._listeners.remove(update_callback)

    @callback
    def _notify_listeners(self) -> None:
        for update_callback in list(self._listeners):
            update_callback()

    def _is_held(self, announcement: Announcement, now: datetime) -> bool:
        return (
            not announcement.urgent
            and not announcement.ignore_quiet_hours
            and self.manager.in_quiet_hours(now)
        )

    async def async_announce(
        self, announcement: Announcement, cooldown: timedelta | None = None
    ) -> bool:
        """Queue an announcement. Returns False if it was suppressed."""
        announcement.message = clean_message(announcement.message)
        if not announcement.message:
            return False
        now = dt_util.utcnow()

        if announcement.key and cooldown:
            last = self._cooldowns.get(announcement.key)
            if last is not None and now - last < cooldown:
                _LOGGER.debug(
                    "%s: suppressing %r, key %r is cooling down",
                    self.name,
                    announcement.message,
                    announcement.key,
                )
                return False

        if self._is_held(announcement, now) and self.manager.quiet_mode == QUIET_MODE_DROP:
            _LOGGER.debug("%s: dropping %r during quiet hours", self.name, announcement.message)
            return False

        if announcement.key:
            self._cooldowns[announcement.key] = now

        # A newer message with the same key or text replaces the queued one.
        folded = announcement.message.casefold()
        self.pending = [
            queued
            for queued in self.pending
            if queued.message.casefold() != folded
            and (announcement.key is None or queued.key != announcement.key)
        ]
        self.pending.append(announcement)

        if announcement.urgent:
            await self.async_flush()
        else:
            self._schedule(now)
            self._notify_listeners()
        return True

    def cancel_timer(self) -> None:
        """Cancel any scheduled send."""
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    def _schedule(self, now: datetime) -> None:
        if self._batch_started is None:
            self._batch_started = now
        due = min(now + self.manager.batch_window, self._batch_started + self.manager.max_wait)
        self._schedule_at(due)

    def _schedule_at(self, when: datetime) -> None:
        self.cancel_timer()
        self._unsub_timer = async_track_point_in_utc_time(self.hass, self._async_timer_fired, when)

    async def _async_timer_fired(self, _now: datetime) -> None:
        self._unsub_timer = None
        await self.async_flush()

    async def async_flush(self) -> None:
        """Send everything that is not held back by quiet hours."""
        self.cancel_timer()
        self._batch_started = None
        now = dt_util.utcnow()

        ready = [a for a in self.pending if not self._is_held(a, now)]
        held = [a for a in self.pending if self._is_held(a, now)]
        if held and self.manager.quiet_mode == QUIET_MODE_DROP:
            held = []
        self.pending = held
        if held:
            self._schedule_at(self.manager.quiet_hours_end(now))

        if ready:
            await self._async_send([a.message for a in ready])
        self._notify_listeners()

    async def _async_send(self, messages: list[str]) -> None:
        manager = self.manager
        for batch in split_into_batches(messages, self.prefix, manager.max_length):
            text = join_messages(batch)
            subject = build_subject(self.prefix, text)
            try:
                await self.hass.services.async_call(
                    NOTIFY_DOMAIN,
                    manager.notify_service,
                    {"message": text, "title": subject, "target": [manager.recipient]},
                    blocking=True,
                )
            except HomeAssistantError as err:
                self.last_error = str(err)
                _LOGGER.error(
                    "Failed to send %r via notify.%s: %s",
                    subject,
                    manager.notify_service,
                    err,
                )
                continue

            _LOGGER.debug("Sent %r", subject)
            self.last_error = None
            self.last_subject = subject
            self.last_text = text
            self.last_messages = batch
            self.last_sent = dt_util.utcnow()
            self.hass.bus.async_fire(
                EVENT_ANNOUNCED,
                {
                    "zone": self.name,
                    "prefix": self.prefix,
                    "subject": subject,
                    "message": text,
                    "messages": batch,
                },
            )
