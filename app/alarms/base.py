"""Base classes and interfaces for alarm protocols.

Ported from legacy Event Bridge (autocare_event_bridge_2.0).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.schemas.sensor import AlarmMessage


@dataclass
class SensorInfo:
    """Sensor information for alarm protocol handlers.

    Runtime DTO containing sensor configuration for protocol handlers.
    Matches legacy SensorDto structure.
    """

    id: str
    name: str
    type_id: str
    ip: str
    port: int

    # Speaker-specific fields
    max_time: int = 120
    pause_time: int = 2

    # Time restriction fields
    is_time_restricted: bool = False
    time_restricted_start: int = 0  # minutes from midnight
    time_restricted_end: int = 0  # minutes from midnight

    def is_current_time_restricted(self) -> bool:
        """Check if current time falls within restricted period.

        Returns True if alarms should be blocked at current time.
        """
        if not self.is_time_restricted:
            return False

        now = datetime.now()
        current_minutes = now.hour * 60 + now.minute

        # Same start and end means no restriction
        if self.time_restricted_start == self.time_restricted_end:
            return False

        # Normal range (e.g., 09:00 ~ 18:00)
        if self.time_restricted_start < self.time_restricted_end:
            return self.time_restricted_start <= current_minutes <= self.time_restricted_end

        # Overnight range (e.g., 22:00 ~ 06:00)
        return (
            current_minutes >= self.time_restricted_start
            or current_minutes <= self.time_restricted_end
        )


class IAlarm(Protocol):
    """Protocol interface for alarm device handlers.

    Each alarm protocol (MOXA, AEPEL, PATLITE, etc.) must implement this interface.
    """

    async def send(
        self,
        sensor: SensorInfo,
        commands: list[AlarmMessage],
    ) -> None:
        """Send alarm command(s) to the device.

        Args:
            sensor: Target sensor configuration
            commands: List of alarm messages to send
        """
        ...

    async def stop(
        self,
        sensor: SensorInfo,
        alarm: AlarmMessage,
    ) -> None:
        """Stop/reset alarm on the device.

        Args:
            sensor: Target sensor configuration
            alarm: Alarm to stop
        """
        ...
