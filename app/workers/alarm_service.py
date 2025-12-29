"""Alarm service for NATS subscription and device control.

Ported from legacy Event Bridge (autocare_event_bridge_2.0).
Subscribes to alarm.updated topic and manages alarm device lifecycle.
"""

import asyncio
import json
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import nats
from loguru import logger
from nats.aio.client import Client as NatsClient
from nats.aio.msg import Msg
from sqlalchemy import select

from app.alarms import SensorInfo, load_alarm_modules
from app.alarms.aepel_speaker import AEPELSpeakerAlarm
from app.core.config import get_settings
from app.db.session import async_session_maker
from app.models.sensor import Sensor, SensorType
from app.schemas.sensor import AlarmMessage

settings = get_settings()


class AlarmService:
    """NATS subscriber for alarm events with timer-based duration management.

    Subscribes to 'alarm.updated' topic from event-compositor.
    Manages active alarms with duration countdown and triggers device stop commands.

    Usage:
        async with alarm_service_lifespan() as service:
            # Service runs until context exits
            pass
    """

    INTERVAL_MS = 500  # Timer interval for duration countdown

    def __init__(self):
        # sensor_id -> list of AlarmMessage (with duration in ms)
        self._active_sensors: dict[str, list[AlarmMessage]] = defaultdict(list)
        self._client: NatsClient | None = None
        self._stop_event = asyncio.Event()
        self._modules = load_alarm_modules()

        # Sensor cache (loaded on start)
        self._sensors: dict[str, SensorInfo] = {}
        self._sensor_types: dict[str, str] = {}  # type_id -> type_name

    async def start(self) -> None:
        """Start the alarm service.

        Connects to NATS, loads sensor cache, and starts timer loop.
        """
        # Load sensor cache
        await self._load_sensor_cache()

        # Connect to NATS
        self._client = await nats.connect(
            settings.nats_uri,
            reconnect_time_wait=2,
            max_reconnect_attempts=-1,
        )
        logger.info(f"AlarmService connected to NATS at {settings.nats_uri}")

        # Subscribe to alarm.updated
        await self._client.subscribe(
            "alarm.updated",
            cb=self._on_alarm_updated,
        )
        logger.info("AlarmService subscribed to 'alarm.updated'")

        # Start timer loop
        asyncio.create_task(self._timer_loop())

    async def stop(self) -> None:
        """Stop the alarm service.

        Sends stop commands to all active alarms and cleans up resources.
        """
        # Stop all active alarms
        for sensor_id, alarms in list(self._active_sensors.items()):
            for alarm in list(alarms):
                await self._stop_command(sensor_id, alarm)
        self._active_sensors.clear()

        # Cleanup speaker tasks
        for module in self._modules.values():
            if isinstance(module, AEPELSpeakerAlarm):
                await module.cleanup()

        # Stop timer loop
        self._stop_event.set()

        # Disconnect NATS
        if self._client:
            await self._client.drain()
            logger.info("AlarmService disconnected from NATS")

    async def reload_cache(self) -> None:
        """Reload sensor cache from database.

        Call this after sensor configuration changes via API.
        """
        await self._load_sensor_cache()
        logger.info("AlarmService sensor cache reloaded")

    async def _load_sensor_cache(self) -> None:
        """Load sensors and sensor types from database into memory cache."""
        async with async_session_maker() as db:
            # Load sensors
            result = await db.execute(select(Sensor))
            sensors = result.scalars().all()
            self._sensors = {
                sensor.id: SensorInfo(
                    id=sensor.id,
                    name=sensor.name,
                    type_id=sensor.type_id,
                    ip=sensor.ip,
                    port=sensor.port,
                    max_time=sensor.max_time,
                    pause_time=sensor.pause_time,
                    is_time_restricted=sensor.is_time_restricted,
                    time_restricted_start=sensor.time_restricted_start,
                    time_restricted_end=sensor.time_restricted_end,
                )
                for sensor in sensors
            }

            # Load sensor types
            result = await db.execute(select(SensorType))
            sensor_types = result.scalars().all()
            self._sensor_types = {st.id: st.name for st in sensor_types}

        logger.info(
            f"AlarmService cache loaded: {len(self._sensors)} sensors, "
            f"{len(self._sensor_types)} types"
        )

    async def _timer_loop(self) -> None:
        """Timer loop for duration countdown.

        Decrements alarm duration every INTERVAL_MS.
        Removes expired alarms and sends stop commands.
        """
        interval = self.INTERVAL_MS / 1000.0

        while not self._stop_event.is_set():
            await asyncio.sleep(interval)

            to_remove: list[tuple[str, AlarmMessage]] = []

            # Decrement durations
            for sensor_id, alarms in list(self._active_sensors.items()):
                for alarm in list(alarms):
                    alarm.duration -= self.INTERVAL_MS
                    if alarm.duration <= 0:
                        to_remove.append((sensor_id, alarm))

            # Remove expired alarms
            for sensor_id, alarm in to_remove:
                if alarm in self._active_sensors.get(sensor_id, []):
                    self._active_sensors[sensor_id].remove(alarm)
                    logger.info(
                        f"Alarm expired: sensor_id={sensor_id}, "
                        f"typeId={alarm.type_id}, alarmType={alarm.alarm_type}"
                    )

                # Send stop command when all alarms for sensor are cleared
                if not self._active_sensors[sensor_id]:
                    self._active_sensors.pop(sensor_id, None)
                    await self._stop_command(sensor_id, alarm)

    async def _on_alarm_updated(self, msg: Msg) -> None:
        """Handle alarm.updated NATS message.

        Parses alarm messages and triggers device commands.
        """
        try:
            data = json.loads(msg.data.decode())
        except Exception as ex:
            logger.error(f"Failed to deserialize alarm.updated payload: {ex}")
            return

        alarm_msgs = AlarmMessage.list_from_payload(data)
        if not alarm_msgs:
            logger.warning("alarm.updated received empty or invalid payload")
            return

        # Convert duration/regenInterval from seconds to milliseconds
        for alarm in alarm_msgs:
            alarm.duration *= 1000
            alarm.regen_interval *= 1000

        # Group by sensor_id and type_id
        sensor_ids = {a.id for a in alarm_msgs}
        type_ids = {a.type_id for a in alarm_msgs}

        for type_id in type_ids:
            for sensor_id in sensor_ids:
                selected = [
                    a
                    for a in alarm_msgs
                    if a.id == sensor_id and a.type_id == type_id
                ]
                if not selected:
                    continue

                for alarm in selected:
                    alarms = self._active_sensors[sensor_id]
                    old_alarm = next(
                        (
                            x
                            for x in alarms
                            if x.alarm_type == alarm.alarm_type
                            and x.type_id == alarm.type_id
                        ),
                        None,
                    )

                    if old_alarm is None:
                        alarms.append(alarm)
                    else:
                        # If alarm_value changed, stop old alarm first
                        if old_alarm.alarm_value != alarm.alarm_value:
                            await self._stop_command(sensor_id, old_alarm)

                        # Update existing alarm
                        old_alarm.alarm_value = alarm.alarm_value
                        old_alarm.duration = alarm.duration
                        old_alarm.regen_interval = alarm.regen_interval
                        old_alarm.priority = alarm.priority

                # Send command to device
                await self._send_command(sensor_id, selected)
                logger.info(
                    f"Updated alarms: sensor_id={sensor_id}, "
                    f"typeId={type_id}, count={len(self._active_sensors[sensor_id])}"
                )

    def _get_sensor_and_type(
        self, sensor_id: str
    ) -> tuple[SensorInfo, str] | None:
        """Get sensor info and type name from cache.

        Args:
            sensor_id: Sensor ID to look up

        Returns:
            Tuple of (SensorInfo, type_name) or None if not found
        """
        sensor_info = self._sensors.get(sensor_id)
        if sensor_info is None:
            logger.error(f"Unregistered sensor id: {sensor_id}")
            return None

        type_name = self._sensor_types.get(sensor_info.type_id)
        if type_name is None:
            logger.error(f"Unregistered sensor type id: {sensor_info.type_id}")
            return None

        return sensor_info, type_name

    async def _send_command(
        self, sensor_id: str, alarms: list[AlarmMessage]
    ) -> None:
        """Send alarm command to device.

        Args:
            sensor_id: Target sensor ID
            alarms: List of alarm messages to send
        """
        result = self._get_sensor_and_type(sensor_id)
        if result is None:
            return
        sensor_info, type_name = result

        module = self._modules.get(type_name)
        if module is None:
            logger.error(f"No alarm module registered for type '{type_name}'")
            return

        await module.send(sensor_info, alarms)

    async def _stop_command(self, sensor_id: str, alarm: AlarmMessage) -> None:
        """Send stop command to device.

        Args:
            sensor_id: Target sensor ID
            alarm: Alarm to stop
        """
        result = self._get_sensor_and_type(sensor_id)
        if result is None:
            return
        sensor_info, type_name = result

        module = self._modules.get(type_name)
        if module is None:
            logger.error(f"No alarm module registered for type '{type_name}'")
            return

        await module.stop(sensor_info, alarm)


# Global instance for cache reload access
_alarm_service: AlarmService | None = None


def get_alarm_service() -> AlarmService | None:
    """Get the global AlarmService instance.

    Returns None if service is not running.
    """
    return _alarm_service


@asynccontextmanager
async def alarm_service_lifespan() -> AsyncGenerator[AlarmService, None]:
    """Lifespan context manager for AlarmService.

    Usage in FastAPI lifespan:
        async with alarm_service_lifespan() as alarm_service:
            yield
    """
    global _alarm_service

    service = AlarmService()
    _alarm_service = service

    await service.start()
    try:
        yield service
    finally:
        await service.stop()
        _alarm_service = None
