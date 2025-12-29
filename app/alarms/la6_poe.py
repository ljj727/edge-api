"""PATLITE LA6-POE LED signal tower alarm protocol.

Ported from legacy Event Bridge (autocare_event_bridge_2.0).
Uses PNS (PATLITE Network Signal) binary protocol over TCP socket.
"""

import asyncio
import socket
import struct
from contextlib import closing

from loguru import logger

from app.alarms.base import IAlarm, SensorInfo
from app.schemas.sensor import AlarmMessage


class LA6PoeAlarm(IAlarm):
    """PATLITE LA6-POE LED signal tower controller.

    Controls LED colors and buzzer patterns via PNS protocol.
    Uses 'D' command (Detail Run Control) for full state control.
    """

    # PNS Protocol constants
    PNS_PRODUCT_ID = 0x4142  # 'AB' - PATLITE product category
    PNS_DETAIL_RUN_CONTROL_COMMAND = 0x44  # 'D' command
    PNS_CLEAR_COMMAND = 0x43  # 'C' command
    PNS_NAK = 0x15  # Negative acknowledgment

    # Default command: all LEDs off, no blinking, no buzzer
    # [led1, led2, led3, led4, led5, blinking, buzzer]
    DEFAULT_COMMANDS = ["4", "4", "4", "4", "4", "0", "0"]

    def _build_command_array(self, alarms: list[AlarmMessage]) -> list[str]:
        """Build LED/buzzer command array from alarm messages.

        Args:
            alarms: List of alarm messages

        Returns:
            7-element command array [led1-5, blinking, buzzer]
        """
        cmd = self.DEFAULT_COMMANDS.copy()

        for alarm in alarms:
            alarm_type = (alarm.alarm_type or "").upper()
            alarm_value = (alarm.alarm_value or "").upper()

            if alarm_type == "LED":
                if alarm_value == "RED":
                    for i in range(5):
                        cmd[i] = "1"  # Red LED on
                    cmd[5] = "0"  # No blinking
                    cmd[6] = "1"  # Buzzer pattern 1

                elif alarm_value == "YELLOW":
                    for i in range(5):
                        cmd[i] = "2"  # Yellow LED on
                    cmd[5] = "0"
                    cmd[6] = "9"  # Buzzer pattern 9

                elif alarm_value == "GREEN":
                    for i in range(5):
                        cmd[i] = "4"  # Green LED on
                    cmd[5] = "0"

                elif alarm_value == "NONE":
                    for i in range(5):
                        cmd[i] = "1"
                    cmd[5] = "0"

            elif alarm_type == "BUZZER":
                if alarm_value == "OFF":
                    cmd[6] = "0"
                elif alarm_value == "ON":
                    if cmd[6] == "0":
                        cmd[6] = "1"
                elif alarm_value.startswith("PATTERN"):
                    try:
                        pat = int(alarm_value.replace("PATTERN", ""))
                        pat = max(1, min(pat, 3))  # Clamp to 1-3
                        cmd[6] = str(pat)
                    except ValueError:
                        cmd[6] = "1"

        return cmd

    async def _send_pns_command(
        self,
        sensor: SensorInfo,
        send_data: bytes,
    ) -> None:
        """Send binary PNS command and check response.

        Args:
            sensor: Target sensor configuration
            send_data: Binary command data
        """
        def _send():
            with closing(
                socket.create_connection((sensor.ip, sensor.port), timeout=3)
            ) as sock:
                sock.sendall(send_data)

                try:
                    resp = sock.recv(1024)
                except socket.timeout:
                    logger.error("LA6-POE recv timeout. Sensor={}", sensor.name)
                    return

                if not resp:
                    logger.error("LA6-POE empty response. Sensor={}", sensor.name)
                    return

                if resp[0] == self.PNS_NAK:
                    logger.error(
                        "LA6-POE negative acknowledge (NAK) received. Sensor={}",
                        sensor.name,
                    )
                else:
                    logger.debug(
                        "LA6-POE ACK/response received. Sensor={}, Raw={}",
                        sensor.name,
                        resp.hex(),
                    )

        try:
            await asyncio.to_thread(_send)
        except Exception as ex:
            logger.error(
                "Failed to send LA6-POE PNS command. Sensor={}, Error={}",
                sensor.name,
                ex,
            )

    async def _detail_run_control(
        self,
        sensor: SensorInfo,
        cmd: list[str],
    ) -> None:
        """Send Detail Run Control (D) command.

        Args:
            sensor: Target sensor configuration
            cmd: 7-element command array [led1-5, blinking, buzzer]
        """
        try:
            # Convert string array to bytes
            data_bytes = bytes(int(x) for x in cmd)

            # Build PNS packet
            send = bytearray()
            # Product Category (AB), big-endian
            send += struct.pack(">H", self.PNS_PRODUCT_ID)
            # Command identifier (D)
            send.append(self.PNS_DETAIL_RUN_CONTROL_COMMAND)
            # Empty byte
            send.append(0x00)
            # Data size (ushort, big-endian)
            send += struct.pack(">H", len(data_bytes))
            # Data area
            send += data_bytes

            await self._send_pns_command(sensor, bytes(send))

        except Exception as ex:
            logger.error(
                "Exception while building PNS command. Sensor={}, Error={}",
                sensor.name,
                ex,
            )

    async def send(
        self,
        sensor: SensorInfo,
        commands: list[AlarmMessage],
    ) -> None:
        """Send alarm commands to PATLITE LA6-POE.

        Args:
            sensor: Target sensor configuration
            commands: List of alarm messages
        """
        cmd_array = self._build_command_array(commands)
        for alarm in commands:
            logger.info(
                "LA6-POE Request. Type: {:<10}, Payload: {:<5}. Sensor: {}.",
                alarm.alarm_type,
                alarm.alarm_value,
                sensor.name,
            )
        await self._detail_run_control(sensor, cmd_array)

    async def stop(
        self,
        sensor: SensorInfo,
        alarm: AlarmMessage,
    ) -> None:
        """Stop/reset PATLITE LA6-POE to default state.

        Args:
            sensor: Target sensor configuration
            alarm: Alarm being stopped
        """
        cmd_array = self.DEFAULT_COMMANDS.copy()
        logger.info(
            "LA6-POE Stop. Type: {:<10}, Payload: {:<5}. Sensor: {}.",
            alarm.alarm_type,
            alarm.alarm_value,
            sensor.name,
        )
        await self._detail_run_control(sensor, cmd_array)
