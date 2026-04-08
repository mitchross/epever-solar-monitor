"""Modbus RTU client for Epever MPPT charge controllers."""

import array
import fcntl
import logging
import struct
import threading
import time
from typing import Any

from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

from .registers import (
    UNIT_ID,
    REALTIME_REGISTERS,
    STAT_REGISTERS,
    STATUS_REGISTERS,
    SETTINGS_REGISTERS,
    COIL_REGISTERS,
    decode_battery_status,
    decode_charging_status,
)

logger = logging.getLogger(__name__)

# RS485 ioctl constants
SER_RS485_ENABLED = 0x00000001
SER_RS485_RTS_ON_SEND = 0x00000002
SER_RS485_RTS_AFTER_SEND = 0x00000004
TIOCSRS485 = 0x542F


class EpeverClient:
    """Thread-safe Modbus RTU client for Epever MPPT controllers."""

    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200, unit: int = UNIT_ID):
        self.port = port
        self.baudrate = baudrate
        self.unit = unit
        self._lock = threading.Lock()
        self._client: ModbusSerialClient | None = None
        self._last_data: dict[str, Any] = {}
        self._last_settings: dict[str, Any] = {}
        self._last_status: dict[str, Any] = {}
        self._last_read_time: float = 0
        self._connected = False
        self._consecutive_errors = 0

    def connect(self) -> bool:
        """Establish serial connection with RS485 RTS_AFTER_SEND direction control."""
        with self._lock:
            try:
                self._client = ModbusSerialClient(
                    port=self.port,
                    baudrate=self.baudrate,
                    bytesize=8,
                    parity="N",
                    stopbits=1,
                    timeout=1,
                    retries=1,
                )
                self._connected = self._client.connect()
                if self._connected:
                    # Configure RS485 via kernel ioctl - RTS_AFTER_SEND for this adapter
                    ser = self._client.socket
                    buf = array.array("i", [0] * 8)
                    buf[0] = SER_RS485_ENABLED | SER_RS485_RTS_AFTER_SEND
                    buf[1] = 0  # delay_before_send
                    buf[2] = 0  # delay_after_send
                    fcntl.ioctl(ser.fileno(), TIOCSRS485, buf)
                    logger.info(f"Connected to Epever MPPT on {self.port} (RS485 RTS_AFTER_SEND)")
                    self._consecutive_errors = 0
                else:
                    logger.error(f"Failed to connect to {self.port}")
                return self._connected
            except Exception as e:
                logger.error(f"Connection error: {e}")
                self._connected = False
                return False

    def disconnect(self):
        """Close serial connection."""
        with self._lock:
            if self._client:
                self._client.close()
                self._connected = False

    def _read_input_register(self, addr: int, count: int = 1) -> list[int] | None:
        """Read input register(s). Must be called with lock held."""
        try:
            result = self._client.read_input_registers(addr, count=count, slave=self.unit)
            if result.isError():
                self._consecutive_errors += 1
                return None
            self._consecutive_errors = 0
            return result.registers
        except (ModbusException, AttributeError, Exception) as e:
            self._consecutive_errors += 1
            return None

    def _read_holding_register(self, addr: int, count: int = 1) -> list[int] | None:
        """Read holding register(s). Must be called with lock held."""
        try:
            result = self._client.read_holding_registers(addr, count=count, slave=self.unit)
            if result.isError():
                self._consecutive_errors += 1
                return None
            self._consecutive_errors = 0
            return result.registers
        except (ModbusException, AttributeError, Exception) as e:
            self._consecutive_errors += 1
            return None

    def _read_coil(self, addr: int) -> bool | None:
        """Read a single coil. Must be called with lock held."""
        try:
            result = self._client.read_coils(addr, count=1, slave=self.unit)
            if result.isError():
                self._consecutive_errors += 1
                return None
            self._consecutive_errors = 0
            return result.bits[0]
        except (ModbusException, AttributeError, Exception) as e:
            self._consecutive_errors += 1
            return None

    def _decode_value(self, registers: list[int], reg_def: dict) -> float:
        """Decode register value(s) to a float."""
        if reg_def.get("words", 1) == 2:
            raw = (registers[1] << 16) | registers[0]
        else:
            raw = registers[0]
            if reg_def.get("signed") and raw >= 0x8000:
                raw -= 0x10000
        return raw / reg_def.get("scale", 1)

    def read_all(self) -> dict[str, Any]:
        """Read all realtime + stat + status registers. Returns cached data dict.
        
        Fails fast: if 3 consecutive reads fail, assumes controller is offline.
        """
        with self._lock:
            if not self._connected:
                return self._last_data

            data = {}
            self._consecutive_errors = 0

            for name, reg in REALTIME_REGISTERS.items():
                if self._consecutive_errors >= 3:
                    logger.warning("Controller unresponsive (3 consecutive errors), skipping remaining reads")
                    break
                count = reg.get("words", 1)
                regs = self._read_input_register(reg["addr"], count)
                if regs is not None:
                    data[name] = self._decode_value(regs, reg)
                time.sleep(0.02)

            if data:
                for name, reg in STAT_REGISTERS.items():
                    if self._consecutive_errors >= 3:
                        break
                    count = reg.get("words", 1)
                    regs = self._read_input_register(reg["addr"], count)
                    if regs is not None:
                        data[name] = self._decode_value(regs, reg)
                    time.sleep(0.02)

                status = {}
                for name, reg in STATUS_REGISTERS.items():
                    if self._consecutive_errors >= 3:
                        break
                    regs = self._read_input_register(reg["addr"], 1)
                    if regs is not None:
                        raw_val = regs[0]
                        data[f"{name}_raw"] = raw_val
                        if name == "charging_status":
                            status["charging"] = decode_charging_status(raw_val)
                        elif name == "battery_status":
                            status["battery"] = decode_battery_status(raw_val)
                    time.sleep(0.02)
                self._last_status = status

            if data:
                self._last_data = data
                self._last_read_time = time.time()
                logger.info(
                    f"PV: {data.get('pv_voltage', 0):.1f}V {data.get('pv_power', 0):.1f}W | "
                    f"Bat: {data.get('battery_voltage', 0):.2f}V SOC:{data.get('battery_soc', 0):.0f}% | "
                    f"Load: {data.get('load_power', 0):.1f}W"
                )
            else:
                logger.warning("No data received from controller")

            return self._last_data

    def read_settings(self) -> dict[str, Any]:
        """Read all writable settings (holding registers + coils)."""
        with self._lock:
            if not self._connected:
                return self._last_settings

            settings = {}
            self._consecutive_errors = 0

            for name, reg in SETTINGS_REGISTERS.items():
                if self._consecutive_errors >= 3:
                    break
                regs = self._read_holding_register(reg["addr"], 1)
                if regs is not None:
                    settings[name] = self._decode_value(regs, reg)
                time.sleep(0.02)

            if settings:
                for name, reg in COIL_REGISTERS.items():
                    if self._consecutive_errors >= 3:
                        break
                    val = self._read_coil(reg["addr"])
                    if val is not None:
                        settings[name] = val
                    time.sleep(0.02)

            if settings:
                self._last_settings = settings
            return self._last_settings

    # Voltage registers (0x9003-0x900E) must be written as a batch
    VOLTAGE_REGISTERS = [
        "over_voltage_disconnect", "charging_limit_voltage", "over_voltage_reconnect",
        "equalize_charging_voltage", "boost_charging_voltage", "float_charging_voltage",
        "boost_reconnect_voltage", "low_voltage_reconnect", "under_voltage_recover",
        "under_voltage_warning", "low_voltage_disconnect", "discharging_limit_voltage",
    ]

    def write_setting(self, name: str, value: float | int | bool) -> bool:
        """Write a single setting by name. Returns True on success.
        
        Voltage registers (0x9003-0x900E) are written as a batch because
        the Epever controller rejects individual writes (exception code 4).
        """
        if name in SETTINGS_REGISTERS:
            reg = SETTINGS_REGISTERS[name]
            # Voltage registers must be written as a batch
            if name in self.VOLTAGE_REGISTERS:
                return self._write_voltage_batch(name, value)
            raw_value = int(value * reg.get("scale", 1))
            with self._lock:
                try:
                    result = self._client.write_register(reg["addr"], raw_value, slave=self.unit)
                    if result.isError():
                        logger.error(f"Error writing {name}: {result}")
                        return False
                    logger.info(f"Set {name} = {value} (raw: {raw_value})")
                    return True
                except (ModbusException, AttributeError) as e:
                    logger.error(f"Exception writing {name}: {e}")
                    return False

    def _write_voltage_batch(self, name: str, value: float) -> bool:
        """Write a voltage register by reading all 12, updating one, and batch-writing."""
        with self._lock:
            try:
                # Read current values for all 12 voltage registers (0x9003-0x900E)
                result = self._client.read_holding_registers(0x9003, count=12, slave=self.unit)
                if result.isError():
                    logger.error(f'Cannot read voltage registers for batch write: {result}')
                    return False
                values = list(result.registers)
                # Find index of the register to update
                idx = self.VOLTAGE_REGISTERS.index(name)
                reg = SETTINGS_REGISTERS[name]
                raw_value = int(value * reg.get('scale', 1))
                values[idx] = raw_value
                # Write all 12 back as a batch (function 0x10)
                result = self._client.write_registers(0x9003, values, slave=self.unit)
                if result.isError():
                    logger.error(f'Error batch-writing voltage registers: {result}')
                    return False
                logger.info(f'Set {name} = {value} (raw: {raw_value}) via batch write')
                return True
            except (ModbusException, AttributeError) as e:
                logger.error(f'Exception in voltage batch write: {e}')
                return False

        if name in COIL_REGISTERS:
            reg = COIL_REGISTERS[name]
            with self._lock:
                try:
                    result = self._client.write_coil(reg["addr"], bool(value), slave=self.unit)
                    if result.isError():
                        logger.error(f"Error writing coil {name}: {result}")
                        return False
                    logger.info(f"Set {name} = {value}")
                    return True
                except (ModbusException, AttributeError) as e:
                    logger.error(f"Exception writing coil {name}: {e}")
                    return False

        logger.error(f"Unknown setting: {name}")
        return False

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def last_data(self) -> dict:
        return self._last_data

    @property
    def last_status(self) -> dict:
        return self._last_status

    @property
    def last_settings(self) -> dict:
        return self._last_settings

    @property
    def last_read_time(self) -> float:
        return self._last_read_time
