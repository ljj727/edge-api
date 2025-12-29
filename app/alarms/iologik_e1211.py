"""MOXA IoLogik E1211 REST API I/O controller alarm protocol.

Ported from legacy Event Bridge (autocare_event_bridge_2.0).
"""

from enum import IntEnum

import httpx
from loguru import logger

from app.alarms.base import IAlarm, SensorInfo
from app.schemas.sensor import AlarmMessage


class DOPortStatus(IntEnum):
    """Digital output port status."""

    Off = 0
    On = 1


class IoLogikE1211Alarm(IAlarm):
    """MOXA IoLogik E1211 REST API I/O controller.

    Controls digital outputs via MOXA's RESTful API.
    Uses GET/PUT requests to read/write port status.
    """

    async def _get_do_state(
        self,
        ip: str,
        port: int,
        port_index: int,
    ) -> int:
        """Get current digital output state.

        Args:
            ip: Device IP address
            port: Device HTTP port
            port_index: Digital output port index

        Returns:
            Port status (0=Off, 1=On, -1=Error)
        """
        endpoint = f"/api/slot/0/io/do/{port_index}/doStatus"
        url = f"http://{ip}:{port}{endpoint}"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                headers = {"Accept": "vdn.dac.v1/*"}
                response = await client.get(url, headers=headers)

                if not response.is_success:
                    logger.error(
                        "Failed to Get State. Status={}, Body={}",
                        response.status_code,
                        response.text,
                    )
                    return -1

                data = response.json()
                # Structure: { "io": { "do": { "index": { "doStatus": int } } } }
                io = data.get("io", {})
                do_dict = io.get("do", {})
                first_entry = next(iter(do_dict.values()), None)
                if not isinstance(first_entry, dict):
                    return -1
                return int(first_entry.get("doStatus", -1))

        except Exception as ex:
            logger.error("Exception in _get_do_state: {}", ex)
            return -1

    async def _update_do_state(
        self,
        ip: str,
        port: int,
        port_index: int,
        port_status: DOPortStatus,
    ) -> None:
        """Update digital output state.

        Args:
            ip: Device IP address
            port: Device HTTP port
            port_index: Digital output port index
            port_status: Target status (On/Off)
        """
        endpoint = f"/api/slot/0/io/do/{port_index}/doStatus"
        url = f"http://{ip}:{port}{endpoint}"

        payload = {
            "slot": 0,
            "io": {
                "do": {
                    str(port_index): {
                        "doStatus": int(port_status),
                    }
                }
            },
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                headers = {
                    "Accept": "vdn.dac.v1/*",
                    "Content-Type": "application/json",
                }
                response = await client.put(url, json=payload, headers=headers)

                if not response.is_success:
                    logger.error(
                        "Failed to Update State. Status={}, Body={}",
                        response.status_code,
                        response.text,
                    )

        except Exception as ex:
            logger.error("Exception in _update_do_state: {}", ex)

    async def send(
        self,
        sensor: SensorInfo,
        commands: list[AlarmMessage],
    ) -> None:
        """Send alarm commands to MOXA IoLogik E1211.

        Args:
            sensor: Target sensor configuration
            commands: List of alarm messages (port index in alarm_value)
        """
        for alarm in commands:
            try:
                status = DOPortStatus.On
                if alarm.on_off is not None:
                    status = DOPortStatus.On if alarm.on_off == 1 else DOPortStatus.Off

                port_index = int(alarm.alarm_value)
                await self._update_do_state(
                    ip=sensor.ip,
                    port=sensor.port,
                    port_index=port_index,
                    port_status=status,
                )
                logger.info(
                    "Request. Port: {:<2}, Type: {:<10}, Payload: {:<10}. Sensor: {}.",
                    alarm.alarm_value,
                    alarm.alarm_type,
                    status.name,
                    sensor.name,
                )

                # Verify state change
                current_raw = await self._get_do_state(
                    ip=sensor.ip,
                    port=sensor.port,
                    port_index=port_index,
                )
                current = (
                    DOPortStatus.On
                    if current_raw == int(DOPortStatus.On)
                    else DOPortStatus.Off
                )

                if current != status:
                    logger.error(
                        "Failure. Port: {:<2}, Type: {:<10}, Current: {:<10}. Sensor: {}.",
                        alarm.alarm_value,
                        alarm.alarm_type,
                        current.name,
                        sensor.name,
                    )
                else:
                    logger.info(
                        "Success. Port: {:<2}, Type: {:<10}, Current: {:<10}. Sensor: {}.",
                        alarm.alarm_value,
                        alarm.alarm_type,
                        current.name,
                        sensor.name,
                    )

            except Exception as ex:
                logger.error(
                    "Failure to send, Sensor id: {}, Message: {}", alarm.id, ex
                )

    async def stop(
        self,
        sensor: SensorInfo,
        alarm: AlarmMessage,
    ) -> None:
        """Stop alarm on MOXA IoLogik E1211.

        Args:
            sensor: Target sensor configuration
            alarm: Alarm to stop (inverts on_off state)
        """
        try:
            # Invert the state for stop
            status = DOPortStatus.Off
            if alarm.on_off is not None:
                status = DOPortStatus.Off if alarm.on_off == 1 else DOPortStatus.On

            port_index = int(alarm.alarm_value)
            await self._update_do_state(
                ip=sensor.ip,
                port=sensor.port,
                port_index=port_index,
                port_status=status,
            )
            logger.info(
                "Stop Request. Port: {:<2}, Type: {:<10}, Payload: {:<10}. Sensor: {}.",
                alarm.alarm_value,
                alarm.alarm_type,
                status.name,
                sensor.name,
            )

            # Verify state change
            current_raw = await self._get_do_state(
                ip=sensor.ip,
                port=sensor.port,
                port_index=port_index,
            )
            current = (
                DOPortStatus.On
                if current_raw == int(DOPortStatus.On)
                else DOPortStatus.Off
            )

            if current != status:
                logger.error(
                    "Stop Failure. Port: {:<2}, Type: {:<10}, Current: {:<10}. Sensor: {}.",
                    alarm.alarm_value,
                    alarm.alarm_type,
                    current.name,
                    sensor.name,
                )
            else:
                logger.info(
                    "Stop Success. Port: {:<2}, Type: {:<10}, Current: {:<10}. Sensor: {}.",
                    alarm.alarm_value,
                    alarm.alarm_type,
                    current.name,
                    sensor.name,
                )

        except Exception as ex:
            logger.error("Failure to stop, Sensor id: {}, Message: {}", alarm.id, ex)
