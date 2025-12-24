"""Sensors (EventBridge) API endpoints."""

from fastapi import APIRouter, Query

from app.core.deps import CurrentUserRequired
from app.schemas.system import Sensor, SensorType

router = APIRouter()

# Sample sensor types (would come from EventBridge service)
SENSOR_TYPES = [
    SensorType(
        id="speaker",
        name="Speaker",
        protocol=[],
    ),
    SensorType(
        id="moxa",
        name="Moxa IO",
        protocol=[],
    ),
]


@router.get("", response_model=list[Sensor])
async def get_sensors(
    current_user: CurrentUserRequired,
    type_id: str | None = Query(None, alias="typeId"),
) -> list[Sensor]:
    """
    Get available alarm sensors.

    - **typeId**: Filter by sensor type ID
    """
    # TODO: Get sensors from EventBridge service
    return []


@router.get("/types", response_model=list[SensorType])
async def get_sensor_types(
    current_user: CurrentUserRequired,
) -> list[SensorType]:
    """Get available alarm sensor types."""
    return SENSOR_TYPES
