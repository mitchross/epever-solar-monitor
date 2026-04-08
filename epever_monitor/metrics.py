"""Prometheus metrics for Epever MPPT monitoring."""

from prometheus_client import Gauge, Info, CollectorRegistry

# Use a custom registry to avoid default process/platform metrics clutter
REGISTRY = CollectorRegistry()

# ── Realtime Gauges ──────────────────────────────────────────────────────

pv_voltage = Gauge("epever_pv_voltage_volts", "Solar panel voltage", registry=REGISTRY)
pv_current = Gauge("epever_pv_current_amps", "Solar panel current", registry=REGISTRY)
pv_power = Gauge("epever_pv_power_watts", "Solar panel power", registry=REGISTRY)

battery_voltage = Gauge("epever_battery_voltage_volts", "Battery voltage", registry=REGISTRY)
battery_charge_current = Gauge("epever_battery_charge_current_amps", "Battery charging current", registry=REGISTRY)
battery_charge_power = Gauge("epever_battery_charge_power_watts", "Battery charging power", registry=REGISTRY)
battery_soc = Gauge("epever_battery_soc_percent", "Battery state of charge", registry=REGISTRY)
battery_temp = Gauge("epever_battery_temp_celsius", "Battery temperature", registry=REGISTRY)

load_voltage = Gauge("epever_load_voltage_volts", "Load voltage", registry=REGISTRY)
load_current = Gauge("epever_load_current_amps", "Load current", registry=REGISTRY)
load_power = Gauge("epever_load_power_watts", "Load power", registry=REGISTRY)

device_temp = Gauge("epever_device_temp_celsius", "Controller internal temperature", registry=REGISTRY)

# ── Daily Statistics ─────────────────────────────────────────────────────

generated_today = Gauge("epever_generated_energy_today_kwh", "Energy generated today", registry=REGISTRY)
generated_month = Gauge("epever_generated_energy_month_kwh", "Energy generated this month", registry=REGISTRY)
generated_year = Gauge("epever_generated_energy_year_kwh", "Energy generated this year", registry=REGISTRY)
generated_total = Gauge("epever_generated_energy_total_kwh", "Total energy generated", registry=REGISTRY)

consumed_today = Gauge("epever_consumed_energy_today_kwh", "Energy consumed today", registry=REGISTRY)
consumed_month = Gauge("epever_consumed_energy_month_kwh", "Energy consumed this month", registry=REGISTRY)
consumed_year = Gauge("epever_consumed_energy_year_kwh", "Energy consumed this year", registry=REGISTRY)
consumed_total = Gauge("epever_consumed_energy_total_kwh", "Total energy consumed", registry=REGISTRY)

max_pv_voltage_today = Gauge("epever_max_pv_voltage_today_volts", "Max PV voltage today", registry=REGISTRY)
min_pv_voltage_today = Gauge("epever_min_pv_voltage_today_volts", "Min PV voltage today", registry=REGISTRY)
max_battery_voltage_today = Gauge("epever_max_battery_voltage_today_volts", "Max battery voltage today", registry=REGISTRY)
min_battery_voltage_today = Gauge("epever_min_battery_voltage_today_volts", "Min battery voltage today", registry=REGISTRY)

# ── Status ───────────────────────────────────────────────────────────────

charging_state = Gauge("epever_charging_state", "Charging state (0=off,1=float,2=boost,3=equalize)", registry=REGISTRY)
battery_status_raw = Gauge("epever_battery_status_raw", "Battery status register raw value", registry=REGISTRY)
charging_status_raw = Gauge("epever_charging_status_raw", "Charging status register raw value", registry=REGISTRY)

# ── Collector info ───────────────────────────────────────────────────────

collector_info = Info("epever_collector", "Collector metadata", registry=REGISTRY)
scrape_errors = Gauge("epever_scrape_errors_total", "Total number of scrape errors", registry=REGISTRY)

# ── Mapping from data dict keys to gauge objects ─────────────────────────

GAUGE_MAP = {
    "pv_voltage": pv_voltage,
    "pv_current": pv_current,
    "pv_power": pv_power,
    "battery_voltage": battery_voltage,
    "battery_charge_current": battery_charge_current,
    "battery_charge_power": battery_charge_power,
    "battery_soc": battery_soc,
    "battery_temp": battery_temp,
    "load_voltage": load_voltage,
    "load_current": load_current,
    "load_power": load_power,
    "device_temp": device_temp,
    "generated_energy_today": generated_today,
    "generated_energy_month": generated_month,
    "generated_energy_year": generated_year,
    "generated_energy_total": generated_total,
    "consumed_energy_today": consumed_today,
    "consumed_energy_month": consumed_month,
    "consumed_energy_year": consumed_year,
    "consumed_energy_total": consumed_total,
    "max_pv_voltage_today": max_pv_voltage_today,
    "min_pv_voltage_today": min_pv_voltage_today,
    "max_battery_voltage_today": max_battery_voltage_today,
    "min_battery_voltage_today": min_battery_voltage_today,
    "charging_status_raw": charging_status_raw,
    "battery_status_raw": battery_status_raw,
}

CHARGING_STATE_MAP = {"not_charging": 0, "float": 1, "boost": 2, "equalize": 3}


def update_metrics(data: dict, status: dict):
    """Update all Prometheus gauges from the read data."""
    for key, gauge in GAUGE_MAP.items():
        if key in data:
            gauge.set(data[key])

    # Decode charging state from status
    if "charging" in status:
        state_name = status["charging"].get("charging_state", "not_charging")
        charging_state.set(CHARGING_STATE_MAP.get(state_name, -1))
