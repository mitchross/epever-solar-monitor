"""BLE BMS readers for Daly and Victron battery monitors."""

import asyncio
import logging
import struct
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Daly BMS ─────────────────────────────────────────────────────────────

@dataclass
class DalyData:
    voltage: float = 0.0
    current: float = 0.0
    soc: float = 0.0
    max_cell_voltage: float = 0.0
    min_cell_voltage: float = 0.0
    max_cell_number: int = 0
    min_cell_number: int = 0
    cell_delta: float = 0.0
    max_temp: float = 0.0
    min_temp: float = 0.0
    charge_mos: bool = False
    discharge_mos: bool = False
    cycles: int = 0
    timestamp: float = 0.0


class DalyBMSClient:
    """Read Daly BMS data over BLE using the A5 protocol."""

    WRITE_CHAR = "0000fff2-0000-1000-8000-00805f9b34fb"
    NOTIFY_CHAR = "0000fff1-0000-1000-8000-00805f9b34fb"

    def __init__(self, address: str):
        self.address = address
        self.data = DalyData()
        self._responses: dict[int, bytes] = {}

    @staticmethod
    def _build_cmd(cmd_id: int) -> bytes:
        frame = bytearray([0xA5, 0x40, cmd_id, 0x08,
                           0x00, 0x00, 0x00, 0x00,
                           0x00, 0x00, 0x00, 0x00])
        frame.append(sum(frame) & 0xFF)
        return bytes(frame)

    def _handle_notify(self, _sender, data: bytearray):
        if len(data) >= 4 and data[0] == 0xA5:
            self._responses[data[2]] = bytes(data)

    async def read(self) -> DalyData:
        """Connect, read all registers, disconnect. Returns DalyData."""
        from bleak import BleakClient

        try:
            async with BleakClient(self.address, timeout=10) as client:
                if not client.is_connected:
                    logger.warning(f"Daly BMS {self.address}: connection failed")
                    return self.data

                self._responses.clear()
                await client.start_notify(self.NOTIFY_CHAR, self._handle_notify)
                await asyncio.sleep(0.3)

                # Read SOC, cell range, temps, MOS status
                for cmd in [0x90, 0x91, 0x92, 0x93]:
                    await client.write_gatt_char(
                        self.WRITE_CHAR,
                        self._build_cmd(cmd),
                        response=False,
                    )
                    await asyncio.sleep(0.4)

                await client.stop_notify(self.NOTIFY_CHAR)

            self._decode()
            self.data.timestamp = time.time()
            logger.info(
                f"Daly BMS: {self.data.soc:.1f}% {self.data.voltage:.1f}V "
                f"{self.data.current:.1f}A delta={self.data.cell_delta:.4f}V "
                f"{self.data.min_temp:.0f}-{self.data.max_temp:.0f}°C"
            )
        except Exception as e:
            logger.error(f"Daly BMS read error: {e}")

        return self.data

    def _decode(self):
        # 0x90: SOC info
        if 0x90 in self._responses:
            d = self._responses[0x90]
            if len(d) >= 12:
                self.data.voltage = struct.unpack(">H", d[4:6])[0] / 10
                self.data.current = (struct.unpack(">H", d[8:10])[0] - 30000) / 10
                self.data.soc = struct.unpack(">H", d[10:12])[0] / 10

        # 0x91: Cell voltage range
        if 0x91 in self._responses:
            d = self._responses[0x91]
            if len(d) >= 10:
                self.data.max_cell_voltage = struct.unpack(">H", d[4:6])[0] / 1000
                self.data.max_cell_number = d[6]
                self.data.min_cell_voltage = struct.unpack(">H", d[7:9])[0] / 1000
                self.data.min_cell_number = d[9]
                self.data.cell_delta = self.data.max_cell_voltage - self.data.min_cell_voltage

        # 0x92: Temperature range
        if 0x92 in self._responses:
            d = self._responses[0x92]
            if len(d) >= 7:
                self.data.max_temp = d[4] - 40
                self.data.min_temp = d[6] - 40

        # 0x93: MOS status
        if 0x93 in self._responses:
            d = self._responses[0x93]
            if len(d) >= 6:
                self.data.charge_mos = bool(d[4])
                self.data.discharge_mos = bool(d[5])


# ── Victron SmartBatterySense ────────────────────────────────────────────

@dataclass
class VictronData:
    voltage: float = 0.0
    temperature: float = 0.0
    timestamp: float = 0.0


class VictronBLEClient:
    """Read Victron SmartBatterySense data from BLE advertisements.

    Requires the device encryption key from VictronConnect app.
    """

    VICTRON_MANUFACTURER_ID = 0x02E1

    def __init__(self, address: str, encryption_key: str | None = None):
        self.address = address.upper()
        self.encryption_key = encryption_key
        self.data = VictronData()

    async def read(self) -> VictronData:
        """Scan for Victron advertisement and decrypt data."""
        if not self.encryption_key:
            logger.debug("Victron: no encryption key configured, skipping")
            return self.data

        try:
            from victron_ble.devices import detect_device_type
            from victron_ble.scanner import BaseScanner
        except ImportError:
            logger.warning("victron-ble not installed, skipping Victron")
            return self.data

        try:
            from bleak import BleakScanner

            devices = await BleakScanner.discover(timeout=12, return_adv=True)
            found_names = [(a, d.name) for a, (d, _) in devices.items()]
            logger.debug(f"Victron scan found {len(devices)} devices: {found_names}")
            for addr, (dev, adv) in devices.items():
                if addr.upper() == self.address:
                    logger.debug(f"Victron matched {addr}, mfr_data keys: {list(adv.manufacturer_data.keys())}")
                    mfr_data = adv.manufacturer_data.get(self.VICTRON_MANUFACTURER_ID)
                    if not mfr_data:
                        # Try any manufacturer data
                        for mid, mdata in adv.manufacturer_data.items():
                            logger.debug(f"Victron: trying mfr_id={mid} (0x{mid:04X}) len={len(mdata)}")
                            mfr_data = mdata
                            break
                    if mfr_data:
                        try:
                            logger.debug(f"Victron mfr_data: {mfr_data.hex()} ({len(mfr_data)} bytes)")
                            device_klass = detect_device_type(mfr_data)
                            logger.debug(f"Victron device_klass: {device_klass}")
                            if device_klass:
                                parsed = device_klass(self.encryption_key).parse(mfr_data)
                                logger.debug(f"Victron parsed: {type(parsed)}")
                                voltage = parsed.get_voltage()
                                temperature = parsed.get_temperature()
                                try:
                                    self.data.voltage = float(voltage) if voltage is not None else 0.0
                                    self.data.temperature = float(temperature) if temperature is not None else 0.0
                                except Exception as ex2:
                                    logger.error(f"Victron assign error: {ex2} v={voltage!r} t={temperature!r}")
                        except Exception as ex:
                            logger.error(f"Victron decrypt error: {ex}")
                    if self.data.voltage > 0:
                        self.data.timestamp = time.time()
                        logger.info(
                            f"Victron: {self.data.voltage:.2f}V "
                            f"{self.data.temperature:.1f}°C"
                        )
        except Exception as e:
            logger.error(f"Victron read error: {e}")

        return self.data
