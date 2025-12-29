"""AEPEL IP Speaker alarm protocol.

Ported from legacy Event Bridge (autocare_event_bridge_2.0).
Handles priority-based audio playback with time restrictions.
"""

import asyncio
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from loguru import logger

from app.alarms.base import IAlarm, SensorInfo
from app.schemas.sensor import AlarmMessage


@dataclass
class EventAlertState:
    """State information for each alarm event."""

    is_set: bool = False
    last_alert_time: datetime = field(default_factory=lambda: datetime.min)
    last_detected_time: datetime = field(default_factory=datetime.now)
    start_time: datetime = field(default_factory=datetime.now)
    event_interval: float = 3000.0  # ms
    voice_port: str = "1"
    priority: int = 10  # 1~10, 1 is highest


class AlertManager:
    """Manages alarm priority and playback scheduling."""

    MARGIN_TIMEOUT_TIME = 2000  # Communication margin time (ms)

    def __init__(self, max_time_second: int = 120, pause_time_second: int = 0):
        self.max_time_second = max_time_second
        self.pause_time_second = pause_time_second
        self.alert_states: dict[str, EventAlertState] = {}
        self.next_alert = EventAlertState()
        self.next_alert.is_set = False

    def set_settings(self, max_time_second: int, pause_time_second: int) -> None:
        """Update manager settings."""
        self.max_time_second = max_time_second
        self.pause_time_second = pause_time_second

    def add_event(
        self, voice_port: str, priority: int, event_interval: float
    ) -> None:
        """Add or update an alarm event.

        Considers priority and playback interval to determine next playback.
        """
        now = datetime.now()

        if voice_port not in self.alert_states:
            self.alert_states[voice_port] = EventAlertState(
                voice_port=voice_port,
                priority=priority,
                event_interval=event_interval,
            )

        cur_state = self.alert_states[voice_port]
        cur_state.event_interval = event_interval
        cur_state.voice_port = voice_port
        cur_state.priority = priority

        # Check if this is a new event (first detection or timeout)
        timeout_ms = cur_state.event_interval + self.MARGIN_TIMEOUT_TIME
        if cur_state.last_detected_time + timedelta(milliseconds=timeout_ms) < now:
            cur_state.start_time = now

        cur_state.last_detected_time = now

        # Check maxTime exceeded
        if cur_state.start_time + timedelta(seconds=self.max_time_second) < now:
            return

        # Priority comparison
        if self.next_alert.is_set:
            if self.next_alert.priority < priority:
                # Existing alert has higher priority
                return
            elif self.next_alert.priority == priority:
                # Same priority - prefer older last_alert_time
                if self.next_alert.last_alert_time < cur_state.last_alert_time:
                    return

        # Set as next playback target
        self.alert_states[voice_port] = cur_state
        self.next_alert = EventAlertState(
            is_set=True,
            last_alert_time=cur_state.last_alert_time,
            last_detected_time=cur_state.last_detected_time,
            start_time=cur_state.start_time,
            event_interval=cur_state.event_interval,
            voice_port=cur_state.voice_port,
            priority=cur_state.priority,
        )

    def get_next_event(self) -> str:
        """Get next event to play. Returns empty string if none."""
        if not self.next_alert.is_set:
            return ""

        now = datetime.now()

        # Check last detection time
        timeout_ms = self.next_alert.event_interval + self.MARGIN_TIMEOUT_TIME
        if self.next_alert.last_detected_time + timedelta(milliseconds=timeout_ms) < now:
            self.next_alert.is_set = False
            return ""

        # Check maxTime
        if self.next_alert.start_time + timedelta(seconds=self.max_time_second) < now:
            self.next_alert.is_set = False
            return ""

        # Return and reset next event
        self.alert_states[self.next_alert.voice_port].last_alert_time = now
        voice_port = self.next_alert.voice_port
        self.next_alert.is_set = False

        return voice_port

    def exist_next_alert(self) -> bool:
        """Check if there's a pending alert."""
        return self.next_alert.is_set

    def get_pause_time(self) -> int:
        """Get pause time in milliseconds."""
        return self.pause_time_second * 1000


class AEPELSpeakerAlarm(IAlarm):
    """AEPEL IP Speaker alarm module.

    Manages background tasks for continuous audio playback with priority.
    """

    # Authentication credentials
    USERNAME = "admin"
    PASSWORD = "aepel1234"

    def __init__(self):
        # speaker_key (ip:port) -> AlertManager
        self._managers: dict[str, AlertManager] = {}
        # speaker_key -> asyncio.Task
        self._tasks: dict[str, asyncio.Task | None] = {}
        # speaker_key -> running flag
        self._running: dict[str, bool] = {}

    async def _speaker_task(self, speaker_key: str) -> None:
        """Background task for speaker playback.

        Continuously checks AlertManager for pending events and plays them.
        """
        while self._running.get(speaker_key, False):
            try:
                manager = self._managers.get(speaker_key)
                if not manager or not manager.exist_next_alert():
                    await asyncio.sleep(0.25)
                    continue

                alarm_value = manager.get_next_event()
                if not alarm_value:
                    continue

                # HTTP request: GET http://{ip}:{port}/play/{alarmValue}/1
                url = f"http://{speaker_key}/play/{alarm_value}/1"

                def _send_request():
                    """Send multipart form data with GET request (speaker requirement)."""
                    boundary = "----WebKitFormBoundary" + "".join(
                        [str(i) for i in range(15)]
                    )
                    body_parts = [
                        f"--{boundary}\r\n".encode(),
                        b'Content-Disposition: form-data; name="username"\r\n\r\n',
                        f"{self.USERNAME}\r\n".encode(),
                        f"--{boundary}\r\n".encode(),
                        b'Content-Disposition: form-data; name="password"\r\n\r\n',
                        f"{self.PASSWORD}\r\n".encode(),
                        f"--{boundary}--\r\n".encode(),
                    ]
                    body = b"".join(body_parts)

                    # Non-standard: GET request with body (speaker requirement)
                    req = urllib.request.Request(url, data=body, method="GET")
                    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
                    req.add_header("Content-Length", str(len(body)))

                    with urllib.request.urlopen(req, timeout=5) as response:
                        if response.status >= 400:
                            raise Exception(
                                f"HTTP {response.status}: {response.read().decode()}"
                            )
                        return response

                await asyncio.to_thread(_send_request)

                # Wait for pause_time
                pause_ms = manager.get_pause_time()
                if pause_ms > 0:
                    await asyncio.sleep(pause_ms / 1000.0)

            except Exception as ex:
                logger.error("Failed to Send. Speaker={}, Error={}", speaker_key, ex)

            await asyncio.sleep(0.25)

    async def send(
        self,
        sensor: SensorInfo,
        commands: list[AlarmMessage],
    ) -> None:
        """Send alarm to AEPEL IP Speaker.

        Starts background task if not running and adds event to queue.
        """
        speaker_key = f"{sensor.ip}:{sensor.port}"

        # Check time restriction
        if sensor.is_current_time_restricted():
            if commands:
                logger.info(
                    "Restricted Time Requests ignored. Port: {:<2}, Type: {:<10}. Sensor: {}.",
                    commands[0].alarm_value,
                    commands[0].alarm_type,
                    sensor.name,
                )
            return

        try:
            # Create task if not exists
            if speaker_key not in self._tasks or self._tasks[speaker_key] is None:
                self._managers[speaker_key] = AlertManager(
                    sensor.max_time, sensor.pause_time
                )
                self._running[speaker_key] = True
                self._tasks[speaker_key] = asyncio.create_task(
                    self._speaker_task(speaker_key)
                )

            # Update settings
            manager = self._managers[speaker_key]
            manager.set_settings(sensor.max_time, sensor.pause_time)

            # Add event (first command only, matching legacy)
            if commands:
                alarm = commands[0]
                manager.add_event(
                    alarm.alarm_value,
                    alarm.priority,
                    alarm.regen_interval,
                )

                logger.info(
                    "Send Request. Port: {:<2}, Type: {:<10}. Sensor: {}.",
                    alarm.alarm_value,
                    alarm.alarm_type,
                    sensor.name,
                )

        except Exception as ex:
            logger.error("Failed to Send. Sensor={}, Error={}", sensor.name, ex)

    async def stop(
        self,
        sensor: SensorInfo,
        alarm: AlarmMessage,
    ) -> None:
        """Stop alarm on speaker.

        Cleans up tasks if too many are running.
        """
        try:
            speaker_key = f"{sensor.ip}:{sensor.port}"

            # Clean up if too many tasks
            if len(self._tasks) > 16:
                keys_to_remove = list(self._tasks.keys())
                for key in keys_to_remove:
                    await self._remove_speaker_info(key)

        except Exception as ex:
            logger.error("Failed to Stop. Sensor={}, Error={}", sensor.name, ex)

    async def _remove_speaker_info(self, speaker_key: str) -> None:
        """Remove speaker task and manager."""
        self._running[speaker_key] = False

        task = self._tasks.get(speaker_key)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._tasks.pop(speaker_key, None)
        self._running.pop(speaker_key, None)
        self._managers.pop(speaker_key, None)

    async def cleanup(self) -> None:
        """Cleanup all speaker tasks (called on shutdown)."""
        for key in list(self._running.keys()):
            self._running[key] = False

        tasks_to_cancel = []
        for task in self._tasks.values():
            if task and not task.done():
                task.cancel()
                tasks_to_cancel.append(task)

        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

        self._tasks.clear()
        self._running.clear()
        self._managers.clear()
