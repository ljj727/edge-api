"""Sensor models for alarm device management.

Ported from legacy Event Bridge (autocare_event_bridge_2.0).
Manages physical alarm devices: I/O controllers, speakers, LED lights.
"""

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Sensor(Base):
    """Sensor (alarm device) configuration.

    Represents a physical alarm device that can be controlled via various protocols.
    Matches legacy SensorEntity structure.

    Attributes:
        id: Unique sensor identifier
        name: Human-readable sensor name
        type_id: Reference to SensorType (determines protocol)
        ip: Device IP address
        port: Device port number
        max_time: Maximum alarm duration in seconds (speaker only)
        pause_time: Pause between alarm repeats in seconds (speaker only)
        is_time_restricted: Whether time-based restrictions apply
        time_restricted_start: Start time in minutes from midnight (0-1440)
        time_restricted_end: End time in minutes from midnight (0-1440)
    """

    __tablename__ = "sensors"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type_id: Mapped[str] = mapped_column(String(255), nullable=False)
    ip: Mapped[str] = mapped_column(String(255), nullable=False, default="0.0.0.0")
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=80)

    # Speaker-specific fields
    max_time: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    pause_time: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    # Time restriction fields
    is_time_restricted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    time_restricted_start: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )  # minutes from midnight
    time_restricted_end: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )  # minutes from midnight


class SensorType(Base):
    """Sensor type definition with protocol mapping.

    Defines the protocol used to communicate with a category of sensors.
    Matches legacy SensorTypeEntity structure.

    Supported protocols:
        - Adam6050: Modbus TCP I/O controller (placeholder)
        - IoLogik_E1211: MOXA REST API I/O controller
        - AEPEL_IPSpeaker: HTTP-based IP speaker
        - LA6_POE: PATLITE socket-based LED signal tower

    Attributes:
        id: Unique type identifier (e.g., "type_1")
        name: Protocol name (e.g., "IoLogik_E1211")
        protocol: Additional protocol details (JSON or text)
    """

    __tablename__ = "sensor_types"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    protocol: Mapped[str] = mapped_column(Text, nullable=False, default="")
