"""Adam6050 Modbus TCP I/O controller alarm protocol.

Placeholder implementation - actual Modbus TCP control to be added if needed.
Ported from legacy Event Bridge (autocare_event_bridge_2.0).
"""

from loguru import logger

from app.alarms.base import IAlarm, SensorInfo
from app.schemas.sensor import AlarmMessage


class Adam6050Alarm(IAlarm):
    """Advantech Adam-6050 Modbus/TCP digital output controller.

    Currently a placeholder that logs operations.
    Actual Modbus TCP implementation can be added when hardware is available.
    """

    async def send(
        self,
        sensor: SensorInfo,
        commands: list[AlarmMessage],
    ) -> None:
        """Send alarm commands to Adam-6050.

        Args:
            sensor: Target sensor configuration
            commands: List of alarm messages to send
        """
        for alarm in commands:
            logger.info(
                "[Adam6050] Send (noop). Port={}, Type={}, OnOff={}, Sensor={}",
                alarm.alarm_value,
                alarm.alarm_type,
                alarm.on_off if alarm.on_off is not None else "N/A",
                sensor.name,
            )

    async def stop(
        self,
        sensor: SensorInfo,
        alarm: AlarmMessage,
    ) -> None:
        """Stop alarm on Adam-6050.

        Args:
            sensor: Target sensor configuration
            alarm: Alarm to stop
        """
        logger.info(
            "[Adam6050] Stop (noop). Port={}, Type={}, OnOff={}, Sensor={}",
            alarm.alarm_value,
            alarm.alarm_type,
            alarm.on_off if alarm.on_off is not None else "N/A",
            sensor.name,
        )
