"""Prometheus metrics for BMS devices."""

from prometheus_client import Gauge
from .metrics import REGISTRY

# ── Daly BMS Gauges ──────────────────────────────────────────────────────

daly_voltage = Gauge("daly_bms_voltage_volts", "Daly BMS total voltage", registry=REGISTRY)
daly_current = Gauge("daly_bms_current_amps", "Daly BMS current (positive=charging)", registry=REGISTRY)
daly_soc = Gauge("daly_bms_soc_percent", "Daly BMS state of charge", registry=REGISTRY)
daly_max_cell = Gauge("daly_bms_max_cell_voltage_volts", "Daly BMS highest cell voltage", registry=REGISTRY)
daly_min_cell = Gauge("daly_bms_min_cell_voltage_volts", "Daly BMS lowest cell voltage", registry=REGISTRY)
daly_cell_delta = Gauge("daly_bms_cell_delta_volts", "Daly BMS cell voltage imbalance", registry=REGISTRY)
daly_max_temp = Gauge("daly_bms_max_temp_celsius", "Daly BMS max temperature", registry=REGISTRY)
daly_min_temp = Gauge("daly_bms_min_temp_celsius", "Daly BMS min temperature", registry=REGISTRY)
daly_charge_mos = Gauge("daly_bms_charge_mos", "Daly BMS charge MOSFET (1=on)", registry=REGISTRY)
daly_discharge_mos = Gauge("daly_bms_discharge_mos", "Daly BMS discharge MOSFET (1=on)", registry=REGISTRY)

# ── Victron Gauges ───────────────────────────────────────────────────────

victron_voltage = Gauge("victron_battery_voltage_volts", "Victron SmartBatterySense voltage", registry=REGISTRY)
victron_temp = Gauge("victron_battery_temp_celsius", "Victron SmartBatterySense temperature", registry=REGISTRY)


def update_daly_metrics(data):
    """Update Daly BMS Prometheus gauges."""
    if data.timestamp == 0:
        return
    daly_voltage.set(data.voltage)
    daly_current.set(data.current)
    daly_soc.set(data.soc)
    daly_max_cell.set(data.max_cell_voltage)
    daly_min_cell.set(data.min_cell_voltage)
    daly_cell_delta.set(data.cell_delta)
    daly_max_temp.set(data.max_temp)
    daly_min_temp.set(data.min_temp)
    daly_charge_mos.set(int(data.charge_mos))
    daly_discharge_mos.set(int(data.discharge_mos))


def update_victron_metrics(data):
    """Update Victron Prometheus gauges."""
    if data.timestamp == 0:
        return
    victron_voltage.set(data.voltage)
    victron_temp.set(data.temperature)
