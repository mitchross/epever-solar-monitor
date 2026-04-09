"""Epever Solar MPPT Monitor - FastAPI + Prometheus exporter."""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from prometheus_client import generate_latest
from pydantic import BaseModel

from .modbus_client import EpeverClient
from .metrics import REGISTRY, update_metrics, scrape_errors, collector_info
from .registers import (
    SETTINGS_REGISTERS,
    COIL_REGISTERS,
    BATTERY_TYPE_MAP,
    REALTIME_REGISTERS,
    STAT_REGISTERS,
)
from .ble_bms import DalyBMSClient, VictronBLEClient
from .bms_metrics import update_daly_metrics, update_victron_metrics, update_bank_metrics

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("epever")

# Configuration from environment
SERIAL_PORT = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
BAUD_RATE = int(os.getenv("BAUD_RATE", "115200"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))

# BLE BMS configuration
DALY_BMS_ADDRESS = os.getenv("DALY_BMS_ADDRESS", "")
VICTRON_ADDRESS = os.getenv("VICTRON_ADDRESS", "")
VICTRON_KEY = os.getenv("VICTRON_ENCRYPTION_KEY", "")
BLE_POLL_INTERVAL = int(os.getenv("BLE_POLL_INTERVAL", "30"))

client = EpeverClient(port=SERIAL_PORT, baudrate=BAUD_RATE)

# BLE clients (initialized if addresses are configured)
daly_client = DalyBMSClient(DALY_BMS_ADDRESS) if DALY_BMS_ADDRESS else None
victron_client = VictronBLEClient(VICTRON_ADDRESS, VICTRON_KEY) if VICTRON_ADDRESS else None


async def poll_loop():
    """Background task that reads MPPT data on a fixed interval."""
    while True:
        try:
            if not client.connected:
                logger.info("Attempting to connect...")
                if not client.connect():
                    logger.warning(f"Connection failed, retrying in {POLL_INTERVAL}s")
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

            data = client.read_all()
            status = client.last_status
            update_metrics(data, status)

            if data:
                logger.debug(
                    f"PV: {data.get('pv_voltage', 0):.1f}V {data.get('pv_power', 0):.1f}W | "
                    f"Bat: {data.get('battery_voltage', 0):.2f}V SOC:{data.get('battery_soc', 0):.0f}% | "
                    f"Load: {data.get('load_power', 0):.1f}W"
                )
        except Exception as e:
            logger.error(f"Poll error: {e}")
            scrape_errors.inc()
            # Try to reconnect on next iteration
            client.disconnect()

        await asyncio.sleep(POLL_INTERVAL)



async def ble_poll_loop():
    """Background task that reads BLE BMS devices on a fixed interval.
    
    Daly requires a BLE connection (takes ~8s), Victron uses passive
    advertisement scanning (takes ~8s). We add a delay between them
    so the BLE adapter can reset between connection and scan modes.
    """
    while True:
        try:
            # Victron first (passive BLE scan) before Daly (active connection)
            # to avoid BLE adapter contention
            if victron_client:
                data = await victron_client.read()
                update_victron_metrics(data)
                await asyncio.sleep(2)
            if daly_client:
                data = await daly_client.read()
                update_daly_metrics(data)
                # Update estimated bank metrics (Daly SOC + MPPT charge data)
                update_bank_metrics(daly_client.data, client.last_data)
        except Exception as e:
            logger.error(f"BLE poll error: {e}")
        await asyncio.sleep(BLE_POLL_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background polling on app startup."""
    collector_info.info({
        "version": "1.0.0",
        "serial_port": SERIAL_PORT,
        "poll_interval": str(POLL_INTERVAL),
    })
    task = asyncio.create_task(poll_loop())
    ble_task = None
    if daly_client or victron_client:
        ble_task = asyncio.create_task(ble_poll_loop())
        devices = []
        if daly_client:
            devices.append(f"Daly={DALY_BMS_ADDRESS}")
        if victron_client:
            devices.append(f"Victron={VICTRON_ADDRESS}")
        logger.info(f"BLE BMS polling started: {", ".join(devices)} interval={BLE_POLL_INTERVAL}s")
    logger.info(f"Epever Solar Monitor started (port={SERIAL_PORT}, interval={POLL_INTERVAL}s)")
    yield
    task.cancel()
    if ble_task:
        ble_task.cancel()
    client.disconnect()


app = FastAPI(
    title="Epever Solar MPPT Monitor",
    description="Monitor and control Epever/EPSolar MPPT charge controllers via Modbus RTU",
    version="1.0.0",
    lifespan=lifespan,
)

STATIC_DIR = Path(__file__).parent / 'static'
app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')


@app.get('/', include_in_schema=False)
def dashboard():
    return FileResponse(str(STATIC_DIR / 'index.html'))


# ── Prometheus metrics endpoint ──────────────────────────────────────────

@app.get("/metrics", response_class=PlainTextResponse, tags=["Prometheus"])
def metrics():
    """Prometheus metrics endpoint."""
    return generate_latest(REGISTRY).decode()


# ── Status / health ─────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health():
    """Health check."""
    return {
        "status": "healthy" if client.connected else "disconnected",
        "serial_port": SERIAL_PORT,
        "last_read": client.last_read_time,
        "seconds_since_read": round(time.time() - client.last_read_time, 1) if client.last_read_time else None,
    }


@app.get("/status", tags=["Realtime"])
def status():
    """Current MPPT status - all realtime data + decoded status."""
    data = client.last_data
    if not data:
        raise HTTPException(status_code=503, detail="No data available yet")
    return {
        "realtime": data,
        "status": client.last_status,
        "timestamp": client.last_read_time,
    }


# ── Settings read/write ─────────────────────────────────────────────────

@app.get("/settings", tags=["Settings"])
def get_settings():
    """Read all current MPPT settings."""
    settings = client.read_settings()
    if not settings:
        raise HTTPException(status_code=503, detail="Could not read settings")

    # Annotate with metadata
    annotated = {}
    for name, value in settings.items():
        reg = SETTINGS_REGISTERS.get(name) or COIL_REGISTERS.get(name, {})
        annotated[name] = {
            "value": value,
            "unit": reg.get("unit", ""),
            "help": reg.get("help", ""),
        }
        if name == "battery_type":
            annotated[name]["value_name"] = BATTERY_TYPE_MAP.get(int(value), "unknown")
    return annotated


class SettingUpdate(BaseModel):
    value: float | int | bool

    model_config = {"json_schema_extra": {"examples": [{"value": 14.4}]}}


@app.post("/settings/{setting_name}", tags=["Settings"])
def update_setting(setting_name: str, body: SettingUpdate):
    """Update a single MPPT setting.

    Available settings (holding registers):
    - battery_type, battery_capacity, boost_charging_voltage, float_charging_voltage
    - equalize_charging_voltage, over_voltage_disconnect, charging_limit_voltage
    - low_voltage_disconnect, low_voltage_reconnect, under_voltage_warning
    - under_voltage_recover, over_voltage_reconnect, boost_reconnect_voltage
    - discharging_limit_voltage, temp_compensation_coeff

    Available settings (coils):
    - manual_load_control, load_default_mode, enable_load_test, force_load
    """
    all_settings = {**SETTINGS_REGISTERS, **COIL_REGISTERS}
    if setting_name not in all_settings:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown setting '{setting_name}'. Available: {list(all_settings.keys())}",
        )

    success = client.write_setting(setting_name, body.value)
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to write {setting_name}")

    return {
        "setting": setting_name,
        "value": body.value,
        "status": "written",
    }


@app.get("/bms", tags=["BMS"])
def bms_status():
    """Current BMS data from Daly and Victron BLE devices."""
    result = {}
    if daly_client and daly_client.data.timestamp > 0:
        d = daly_client.data
        result["daly"] = {
            "voltage": d.voltage,
            "current": d.current,
            "soc": d.soc,
            "max_cell_voltage": d.max_cell_voltage,
            "min_cell_voltage": d.min_cell_voltage,
            "cell_delta": round(d.cell_delta, 4),
            "max_temp": d.max_temp,
            "min_temp": d.min_temp,
            "charge_mos": d.charge_mos,
            "discharge_mos": d.discharge_mos,
            "timestamp": d.timestamp,
        }
    if victron_client and victron_client.data.timestamp > 0:
        v = victron_client.data
        result["victron"] = {
            "voltage": v.voltage,
            "temperature": v.temperature,
            "timestamp": v.timestamp,
        }
    if not result:
        return {"message": "No BMS devices configured or no data yet"}
    return result


@app.get("/registers", tags=["Reference"])
def list_registers():
    """List all known registers and their metadata."""
    return {
        "realtime": {k: {kk: vv for kk, vv in v.items() if kk != "addr"} for k, v in REALTIME_REGISTERS.items()},
        "statistics": {k: {kk: vv for kk, vv in v.items() if kk != "addr"} for k, v in STAT_REGISTERS.items()},
        "settings": {k: {kk: vv for kk, vv in v.items() if kk != "addr"} for k, v in SETTINGS_REGISTERS.items()},
        "coils": {k: {kk: vv for kk, vv in v.items() if kk != "addr"} for k, v in COIL_REGISTERS.items()},
    }
