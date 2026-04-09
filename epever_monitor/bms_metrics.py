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


# ── Estimated Bank Gauges ─────────────────────────────────────────────

bank_estimated_soc = Gauge("battery_bank_estimated_soc_percent", "Estimated battery bank SOC (from Daly BMS coulomb counting)", registry=REGISTRY)
bank_discharge_power = Gauge("battery_bank_discharge_power_watts", "Estimated discharge power (Daly voltage x current when discharging)", registry=REGISTRY)
bank_charge_power = Gauge("battery_bank_charge_power_watts", "Current charge power from MPPT", registry=REGISTRY)
bank_net_power = Gauge("battery_bank_net_power_watts", "Net power flow (positive=charging, negative=discharging)", registry=REGISTRY)


def update_victron_metrics(data):
    """Update Victron Prometheus gauges."""
    if data.timestamp == 0:
        return
    victron_voltage.set(data.voltage)
    victron_temp.set(data.temperature)


def update_bank_metrics(daly_data, mppt_data):
    """Update estimated bank metrics from best available sources.
    
    SOC: Uses Daly BMS coulomb counting (most accurate).
    Power: Uses Daly current for discharge, MPPT for charge.
    """
    if daly_data and daly_data.timestamp > 0:
        bank_estimated_soc.set(daly_data.soc)
        
        # Discharge power from Daly (current is negative when discharging)
        if daly_data.current < 0:
            discharge_w = daly_data.voltage * abs(daly_data.current)
            bank_discharge_power.set(round(discharge_w, 1))
        else:
            bank_discharge_power.set(0)
    
    if mppt_data:
        charge_w = mppt_data.get("battery_charge_power", 0)
        bank_charge_power.set(charge_w)
        
        # Net power: charge minus discharge
        daly_current = daly_data.current if (daly_data and daly_data.timestamp > 0) else 0
        daly_voltage = daly_data.voltage if (daly_data and daly_data.timestamp > 0) else 0
        net = charge_w + (daly_voltage * daly_current)  # current is already signed
        bank_net_power.set(round(net, 1))
