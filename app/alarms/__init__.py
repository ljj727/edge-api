"""Alarm protocol modules for physical device control.

Ported from legacy Event Bridge (autocare_event_bridge_2.0).

Supported protocols:
    - Adam6050: Advantech Modbus TCP I/O controller (placeholder)
    - IoLogik_E1211: MOXA REST API I/O controller
    - AEPEL_IPSpeaker: HTTP-based IP speaker with priority queue
    - LA6_POE: PATLITE PNS socket-based LED signal tower
"""

from app.alarms.adam6050 import Adam6050Alarm
from app.alarms.aepel_speaker import AEPELSpeakerAlarm
from app.alarms.base import IAlarm, SensorInfo
from app.alarms.iologik_e1211 import IoLogikE1211Alarm
from app.alarms.la6_poe import LA6PoeAlarm


def load_alarm_modules() -> dict[str, IAlarm]:
    """Load all alarm protocol modules.

    Returns:
        Dictionary mapping sensor type name to alarm handler instance.
        Key format matches SensorType.name in database.
    """
    return {
        "Adam6050": Adam6050Alarm(),
        "IoLogik_E1211": IoLogikE1211Alarm(),
        "AEPEL_IPSpeaker": AEPELSpeakerAlarm(),
        "LA6_POE": LA6PoeAlarm(),
    }


__all__ = [
    "Adam6050Alarm",
    "AEPELSpeakerAlarm",
    "IAlarm",
    "IoLogikE1211Alarm",
    "LA6PoeAlarm",
    "SensorInfo",
    "load_alarm_modules",
]
