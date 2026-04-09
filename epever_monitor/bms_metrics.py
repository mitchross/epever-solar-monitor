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

# ── Estimated Bank Gauges ─────────────────────────────────────────────
# The Daly BMS sits on one 100Ah battery in a 300Ah parallel bank.
# We estimate total bank current by scaling: bank = daly x (total_ah / daly_ah)

BANK_TOTAL_AH = 300  # 100 + 100 + 50 + 50
DALY_BATTERY_AH = 100
BANK_SCALE_FACTOR = BANK_TOTAL_AH / DALY_BATTERY_AH  # 3.0

bank_estimated_soc = Gauge("battery_bank_estimated_soc_percent", "Estimated battery bank SOC (from Daly BMS coulomb counting)", registry=REGISTRY)
bank_voltage = Gauge("battery_bank_voltage_volts", "Battery bank voltage (shared parallel voltage)", registry=REGISTRY)
bank_estimated_current = Gauge("battery_bank_estimated_current_amps", "Estimated total bank current (Daly x3, positive=charging)", registry=REGISTRY)
bank_estimated_discharge_current = Gauge("battery_bank_estimated_discharge_amps", "Estimated total discharge current", registry=REGISTRY)
bank_estimated_charge_current = Gauge("battery_bank_estimated_charge_amps", "Charge current from MPPT", registry=REGISTRY)
bank_discharge_power = Gauge("battery_bank_discharge_power_watts", "Estimated total discharge power", registry=REGISTRY)
bank_charge_power = Gauge("battery_bank_charge_power_watts", "Charge power from MPPT", registry=REGISTRY)
bank_net_power = Gauge("battery_bank_net_power_watts", "Net power flow (positive=charging, negative=discharging)", registry=REGISTRY)
bank_daily_charge_kwh = Gauge("battery_bank_daily_charge_kwh", "Energy charged today from MPPT", registry=REGISTRY)
bank_daily_consumed_kwh = Gauge("battery_bank_daily_consumed_kwh", "Energy consumed today from MPPT", registry=REGISTRY)


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


def update_bank_metrics(daly_data, mppt_data):
    """Update estimated bank metrics.

    Current estimation: Daly measures one 100Ah battery in a 300Ah parallel bank.
    Total bank current ~ Daly current x 3 (ratio of total/daly capacity).

    Example: Daly reads -0.9A (discharging one battery)
    -> Estimated bank total: -2.7A
    -> At 13.2V: ~35.6W total discharge
    -> When running the 2000W inverter: Daly might read -55A -> bank ~165A -> ~2178W
    """
    daly_ok = daly_data and daly_data.timestamp > 0

    if daly_ok:
        # SOC from Daly (coulomb counting, most accurate)
        bank_estimated_soc.set(daly_data.soc)
        bank_voltage.set(daly_data.voltage)

        # Estimate total bank current (Daly sees ~1/3 of the flow)
        est_total_current = daly_data.current * BANK_SCALE_FACTOR
        bank_estimated_current.set(round(est_total_current, 1))

        # Discharge estimates (current is negative when discharging)
        if daly_data.current < 0:
            est_discharge_a = abs(est_total_current)
            est_discharge_w = daly_data.voltage * est_discharge_a
            bank_estimated_discharge_current.set(round(est_discharge_a, 1))
            bank_discharge_power.set(round(est_discharge_w, 1))
        else:
            bank_estimated_discharge_current.set(0)
            bank_discharge_power.set(0)

    if mppt_data:
        # Charge from MPPT (exact, not estimated)
        charge_a = mppt_data.get("battery_charge_current", 0)
        charge_w = mppt_data.get("battery_charge_power", 0)
        bank_estimated_charge_current.set(charge_a)
        bank_charge_power.set(charge_w)

        # Net power: charge minus estimated discharge
        discharge_w = 0
        if daly_ok and daly_data.current < 0:
            discharge_w = daly_data.voltage * abs(daly_data.current) * BANK_SCALE_FACTOR
        net = charge_w - discharge_w
        bank_net_power.set(round(net, 1))

        # Daily energy from MPPT
        bank_daily_charge_kwh.set(mppt_data.get("generated_energy_today", 0))
        bank_daily_consumed_kwh.set(mppt_data.get("consumed_energy_today", 0))
