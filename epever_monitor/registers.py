"""Epever/EPSolar MPPT Modbus register definitions."""

# Modbus unit ID (slave address) - Epever default is 1
UNIT_ID = 1

# ── Input Registers (read-only, function code 0x04) ──────────────────────

# Real-time data
REALTIME_REGISTERS = {
    "pv_voltage":           {"addr": 0x3100, "scale": 100, "unit": "V",  "help": "Solar panel voltage"},
    "pv_current":           {"addr": 0x3101, "scale": 100, "unit": "A",  "help": "Solar panel current"},
    "pv_power":             {"addr": 0x3102, "scale": 100, "unit": "W",  "help": "Solar panel power", "words": 2},
    "battery_voltage":      {"addr": 0x3104, "scale": 100, "unit": "V",  "help": "Battery voltage"},
    "battery_charge_current": {"addr": 0x3105, "scale": 100, "unit": "A", "help": "Battery charging current"},
    "battery_charge_power": {"addr": 0x3106, "scale": 100, "unit": "W",  "help": "Battery charging power", "words": 2},
    "load_voltage":         {"addr": 0x310C, "scale": 100, "unit": "V",  "help": "Load voltage"},
    "load_current":         {"addr": 0x310D, "scale": 100, "unit": "A",  "help": "Load current"},
    "load_power":           {"addr": 0x310E, "scale": 100, "unit": "W",  "help": "Load power", "words": 2},
    "battery_temp":         {"addr": 0x3110, "scale": 100, "unit": "C",  "help": "Battery temperature", "signed": True},
    "device_temp":          {"addr": 0x3111, "scale": 100, "unit": "C",  "help": "Controller internal temperature", "signed": True},
    "battery_soc":          {"addr": 0x311A, "scale": 1,   "unit": "%",  "help": "Battery state of charge"},
    "battery_rated_voltage":{"addr": 0x311D, "scale": 100, "unit": "V",  "help": "Battery system auto-detected voltage"},
}

# Daily/historical statistics
STAT_REGISTERS = {
    "max_pv_voltage_today":     {"addr": 0x3300, "scale": 100, "unit": "V",   "help": "Max PV voltage today"},
    "min_pv_voltage_today":     {"addr": 0x3301, "scale": 100, "unit": "V",   "help": "Min PV voltage today"},
    "max_battery_voltage_today":{"addr": 0x3302, "scale": 100, "unit": "V",   "help": "Max battery voltage today"},
    "min_battery_voltage_today":{"addr": 0x3303, "scale": 100, "unit": "V",   "help": "Min battery voltage today"},
    "consumed_energy_today":    {"addr": 0x3304, "scale": 100, "unit": "kWh", "help": "Consumed energy today", "words": 2},
    "consumed_energy_month":    {"addr": 0x3306, "scale": 100, "unit": "kWh", "help": "Consumed energy this month", "words": 2},
    "consumed_energy_year":     {"addr": 0x3308, "scale": 100, "unit": "kWh", "help": "Consumed energy this year", "words": 2},
    "consumed_energy_total":    {"addr": 0x330A, "scale": 100, "unit": "kWh", "help": "Total consumed energy", "words": 2},
    "generated_energy_today":   {"addr": 0x330C, "scale": 100, "unit": "kWh", "help": "Generated energy today", "words": 2},
    "generated_energy_month":   {"addr": 0x330E, "scale": 100, "unit": "kWh", "help": "Generated energy this month", "words": 2},
    "generated_energy_year":    {"addr": 0x3310, "scale": 100, "unit": "kWh", "help": "Generated energy this year", "words": 2},
    "generated_energy_total":   {"addr": 0x3312, "scale": 100, "unit": "kWh", "help": "Total generated energy", "words": 2},
}

# Status registers
STATUS_REGISTERS = {
    "battery_status":       {"addr": 0x3200, "help": "Battery status bitfield"},
    "charging_status":      {"addr": 0x3201, "help": "Charging equipment status bitfield"},
    "discharging_status":   {"addr": 0x3202, "help": "Discharging equipment status bitfield"},
}

# ── Holding Registers (read/write, function code 0x03/0x06) ──────────────

BATTERY_TYPE_MAP = {0: "user_defined", 1: "sealed", 2: "gel", 3: "flooded", 4: "lithium"}
BATTERY_TYPE_REVERSE = {v: k for k, v in BATTERY_TYPE_MAP.items()}

SETTINGS_REGISTERS = {
    "battery_type":                {"addr": 0x9000, "scale": 1,   "unit": "",   "help": "Battery type (0=User,1=Sealed,2=GEL,3=Flooded,4=Lithium)", "writable": True},
    "battery_capacity":            {"addr": 0x9001, "scale": 1,   "unit": "Ah", "help": "Battery capacity", "writable": True},
    "temp_compensation_coeff":     {"addr": 0x9002, "scale": 100, "unit": "mV/C/2V", "help": "Temperature compensation coefficient", "writable": True},
    "over_voltage_disconnect":     {"addr": 0x9003, "scale": 100, "unit": "V",  "help": "Over voltage disconnect voltage", "writable": True},
    "charging_limit_voltage":      {"addr": 0x9004, "scale": 100, "unit": "V",  "help": "Charging limit voltage", "writable": True},
    "over_voltage_reconnect":      {"addr": 0x9005, "scale": 100, "unit": "V",  "help": "Over voltage reconnect voltage", "writable": True},
    "equalize_charging_voltage":   {"addr": 0x9006, "scale": 100, "unit": "V",  "help": "Equalization charging voltage", "writable": True},
    "boost_charging_voltage":      {"addr": 0x9007, "scale": 100, "unit": "V",  "help": "Boost charging voltage", "writable": True},
    "float_charging_voltage":      {"addr": 0x9008, "scale": 100, "unit": "V",  "help": "Float charging voltage", "writable": True},
    "boost_reconnect_voltage":     {"addr": 0x9009, "scale": 100, "unit": "V",  "help": "Boost reconnect charging voltage", "writable": True},
    "low_voltage_reconnect":       {"addr": 0x900A, "scale": 100, "unit": "V",  "help": "Low voltage reconnect voltage", "writable": True},
    "under_voltage_recover":       {"addr": 0x900B, "scale": 100, "unit": "V",  "help": "Under voltage recover voltage", "writable": True},
    "under_voltage_warning":       {"addr": 0x900C, "scale": 100, "unit": "V",  "help": "Under voltage warning voltage", "writable": True},
    "low_voltage_disconnect":      {"addr": 0x900D, "scale": 100, "unit": "V",  "help": "Low voltage disconnect voltage", "writable": True},
    "discharging_limit_voltage":   {"addr": 0x900E, "scale": 100, "unit": "V",  "help": "Discharging limit voltage", "writable": True},
}

# ── Coil Registers (read/write, function code 0x01/0x05) ──────────────

COIL_REGISTERS = {
    "manual_load_control":  {"addr": 0x0002, "help": "Manual load on/off control", "writable": True},
    "load_default_mode":    {"addr": 0x0003, "help": "Default load control mode", "writable": True},
    "enable_load_test":     {"addr": 0x0005, "help": "Enable load test mode", "writable": True},
    "force_load":           {"addr": 0x0006, "help": "Force load on/off", "writable": True},
}

# Charging status decode helpers
CHARGING_STATE = {0: "not_charging", 1: "float", 2: "boost", 3: "equalize"}

def decode_charging_status(value: int) -> dict:
    """Decode the charging equipment status register."""
    return {
        "input_voltage_status": "normal" if not (value & 0xC000) else "no_power" if (value >> 14) == 2 else "over_voltage",
        "charging_mosfet_short": bool(value & 0x2000),
        "charging_or_anti_reverse_short": bool(value & 0x1000),
        "anti_reverse_mosfet_short": bool(value & 0x0800),
        "input_over_current": bool(value & 0x0400),
        "load_over_current": bool(value & 0x0200),
        "load_short": bool(value & 0x0100),
        "load_mosfet_short": bool(value & 0x0080),
        "pv_input_short": bool(value & 0x0040),
        "charging_state": CHARGING_STATE.get((value >> 2) & 0x03, "unknown"),
        "fault": bool(value & 0x0002),
        "running": bool(value & 0x0001),
    }

def decode_battery_status(value: int) -> dict:
    """Decode the battery status register."""
    voltage_status_map = {0: "normal", 1: "over_voltage", 2: "under_voltage", 3: "low_voltage_disconnect", 4: "fault"}
    temp_status_map = {0: "normal", 1: "over_temp", 2: "low_temp"}
    return {
        "voltage_status": voltage_status_map.get(value & 0x07, "unknown"),
        "temperature_status": temp_status_map.get((value >> 4) & 0x0F, "unknown"),
        "inner_resistance_abnormal": bool(value & 0x0100),
        "wrong_identification": bool(value & 0x8000),
    }
