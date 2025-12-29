"""Sensors (Alarm Devices) API endpoints.

Manages physical alarm devices: I/O controllers, speakers, LED signal towers.
Ported from legacy Event Bridge (autocare_event_bridge_2.0).
"""

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger
from sqlalchemy import select

from app.core.deps import CurrentUserRequired, DBSession
from app.models.sensor import Sensor, SensorType
from app.schemas.sensor import (
    SensorCreate,
    SensorDTO,
    SensorTypeCreate,
    SensorTypeDTO,
    SensorUpdate,
)
from app.workers import get_alarm_service

router = APIRouter()


# ============================================================================
# Sensor Type CRUD (MUST be before /{sensor_id} routes!)
# ============================================================================


@router.get("/types", response_model=list[SensorTypeDTO])
async def get_sensor_types(
    db: DBSession,
    current_user: CurrentUserRequired,
) -> list[SensorTypeDTO]:
    """Get all sensor types."""
    result = await db.execute(select(SensorType))
    sensor_types = result.scalars().all()
    return [SensorTypeDTO.model_validate(st) for st in sensor_types]


@router.get("/types/{type_id}", response_model=SensorTypeDTO)
async def get_sensor_type(
    type_id: str,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> SensorTypeDTO:
    """Get sensor type by ID."""
    result = await db.execute(select(SensorType).where(SensorType.id == type_id))
    sensor_type = result.scalar_one_or_none()

    if not sensor_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor type '{type_id}' not found",
        )

    return SensorTypeDTO.model_validate(sensor_type)


@router.post("/types", response_model=SensorTypeDTO, status_code=status.HTTP_201_CREATED)
async def create_sensor_type(
    data: SensorTypeCreate,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> SensorTypeDTO:
    """
    Create a new sensor type.

    Supported type names (protocol handlers):
    - **Adam6050**: Advantech Modbus TCP I/O controller
    - **IoLogik_E1211**: MOXA REST API I/O controller
    - **AEPEL_IPSpeaker**: HTTP-based IP speaker
    - **LA6_POE**: PATLITE socket-based LED signal tower
    """
    # Generate UUID if not provided
    type_id = data.id or str(uuid.uuid4())

    # Check if type already exists (only if ID was provided)
    if data.id:
        existing = await db.execute(select(SensorType).where(SensorType.id == type_id))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Sensor type '{type_id}' already exists",
            )

    sensor_type = SensorType(
        id=type_id,
        name=data.name,
        protocol=data.protocol,
    )

    db.add(sensor_type)
    await db.commit()
    await db.refresh(sensor_type)

    # Reload alarm service cache
    alarm_service = get_alarm_service()
    if alarm_service:
        await alarm_service.reload_cache()

    logger.info(f"Sensor type created: {sensor_type.id} ({sensor_type.name})")
    return SensorTypeDTO.model_validate(sensor_type)


@router.delete("/types/{type_id}")
async def delete_sensor_type(
    type_id: str,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> dict:
    """Delete sensor type by ID.

    Cannot delete if sensors are using this type.
    """
    # Check if any sensors are using this type
    sensors_result = await db.execute(
        select(Sensor).where(Sensor.type_id == type_id)
    )
    if sensors_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete: sensors are using type '{type_id}'",
        )

    result = await db.execute(select(SensorType).where(SensorType.id == type_id))
    sensor_type = result.scalar_one_or_none()

    if not sensor_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor type '{type_id}' not found",
        )

    await db.delete(sensor_type)
    await db.commit()

    # Reload alarm service cache
    alarm_service = get_alarm_service()
    if alarm_service:
        await alarm_service.reload_cache()

    logger.info(f"Sensor type deleted: {type_id}")
    return {"status": "success"}


@router.post("/types/seed")
async def seed_sensor_types(
    db: DBSession,
    current_user: CurrentUserRequired,
) -> dict:
    """Seed default sensor types.

    Creates the 4 supported sensor types if they don't exist:
    - Adam6050
    - IoLogik_E1211
    - AEPEL_IPSpeaker
    - LA6_POE
    """
    default_types = [
        ("type_adam", "Adam6050", "Advantech Modbus TCP I/O controller"),
        ("type_moxa", "IoLogik_E1211", "MOXA REST API I/O controller"),
        ("type_speaker", "AEPEL_IPSpeaker", "HTTP-based IP speaker"),
        ("type_led", "LA6_POE", "PATLITE socket-based LED signal tower"),
    ]

    created = 0
    for type_id, name, protocol in default_types:
        existing = await db.execute(
            select(SensorType).where(SensorType.name == name)
        )
        if existing.scalar_one_or_none():
            continue

        sensor_type = SensorType(id=type_id, name=name, protocol=protocol)
        db.add(sensor_type)
        created += 1

    await db.commit()

    # Reload alarm service cache
    alarm_service = get_alarm_service()
    if alarm_service:
        await alarm_service.reload_cache()

    logger.info(f"Sensor types seeded: {created} created")
    return {"status": "success", "created": created}


# ============================================================================
# Sensor CRUD
# ============================================================================


@router.get("", response_model=list[SensorDTO])
async def get_sensors(
    db: DBSession,
    current_user: CurrentUserRequired,
    type_id: str | None = Query(None, alias="typeId"),
) -> list[SensorDTO]:
    """
    Get all sensors, optionally filtered by type.

    - **typeId**: Filter by sensor type ID
    """
    if type_id:
        result = await db.execute(select(Sensor).where(Sensor.type_id == type_id))
    else:
        result = await db.execute(select(Sensor))

    sensors = result.scalars().all()
    return [SensorDTO.model_validate(s) for s in sensors]


@router.post("", response_model=SensorDTO, status_code=status.HTTP_201_CREATED)
async def create_sensor(
    data: SensorCreate,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> SensorDTO:
    """
    Create a new sensor.

    - **name**: Human-readable sensor name
    - **typeId**: Reference to SensorType (determines protocol)
    - **ip**: Device IP address
    - **port**: Device port number
    """
    # Generate UUID if not provided
    sensor_id = data.id or str(uuid.uuid4())

    # Check if sensor already exists (only if ID was provided)
    if data.id:
        existing = await db.execute(select(Sensor).where(Sensor.id == sensor_id))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Sensor '{sensor_id}' already exists",
            )

    # Check if sensor type exists
    type_result = await db.execute(
        select(SensorType).where(SensorType.id == data.type_id)
    )
    if not type_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sensor type '{data.type_id}' not found",
        )

    sensor = Sensor(
        id=sensor_id,
        name=data.name,
        type_id=data.type_id,
        ip=data.ip,
        port=data.port,
        max_time=data.max_time,
        pause_time=data.pause_time,
        is_time_restricted=data.is_time_restricted,
        time_restricted_start=data.time_restricted_start,
        time_restricted_end=data.time_restricted_end,
    )

    db.add(sensor)
    await db.commit()
    await db.refresh(sensor)

    # Reload alarm service cache
    alarm_service = get_alarm_service()
    if alarm_service:
        await alarm_service.reload_cache()

    logger.info(f"Sensor created: {sensor.id}")
    return SensorDTO.model_validate(sensor)


@router.get("/{sensor_id}", response_model=SensorDTO)
async def get_sensor(
    sensor_id: str,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> SensorDTO:
    """Get sensor by ID."""
    result = await db.execute(select(Sensor).where(Sensor.id == sensor_id))
    sensor = result.scalar_one_or_none()

    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor '{sensor_id}' not found",
        )

    return SensorDTO.model_validate(sensor)


@router.put("/{sensor_id}", response_model=SensorDTO)
async def update_sensor(
    sensor_id: str,
    data: SensorUpdate,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> SensorDTO:
    """Update sensor configuration."""
    result = await db.execute(select(Sensor).where(Sensor.id == sensor_id))
    sensor = result.scalar_one_or_none()

    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor '{sensor_id}' not found",
        )

    # Update fields if provided
    if data.name is not None:
        sensor.name = data.name
    if data.type_id is not None:
        # Verify sensor type exists
        type_result = await db.execute(
            select(SensorType).where(SensorType.id == data.type_id)
        )
        if not type_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sensor type '{data.type_id}' not found",
            )
        sensor.type_id = data.type_id
    if data.ip is not None:
        sensor.ip = data.ip
    if data.port is not None:
        sensor.port = data.port
    if data.max_time is not None:
        sensor.max_time = data.max_time
    if data.pause_time is not None:
        sensor.pause_time = data.pause_time
    if data.is_time_restricted is not None:
        sensor.is_time_restricted = data.is_time_restricted
    if data.time_restricted_start is not None:
        sensor.time_restricted_start = data.time_restricted_start
    if data.time_restricted_end is not None:
        sensor.time_restricted_end = data.time_restricted_end

    await db.commit()
    await db.refresh(sensor)

    # Reload alarm service cache
    alarm_service = get_alarm_service()
    if alarm_service:
        await alarm_service.reload_cache()

    logger.info(f"Sensor updated: {sensor.id}")
    return SensorDTO.model_validate(sensor)


@router.delete("/{sensor_id}")
async def delete_sensor(
    sensor_id: str,
    db: DBSession,
    current_user: CurrentUserRequired,
) -> dict:
    """Delete sensor by ID."""
    result = await db.execute(select(Sensor).where(Sensor.id == sensor_id))
    sensor = result.scalar_one_or_none()

    if not sensor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensor '{sensor_id}' not found",
        )

    await db.delete(sensor)
    await db.commit()

    # Reload alarm service cache
    alarm_service = get_alarm_service()
    if alarm_service:
        await alarm_service.reload_cache()

    logger.info(f"Sensor deleted: {sensor_id}")
    return {"status": "success"}
