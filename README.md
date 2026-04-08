# Epever Solar Monitor

Modern monitoring and control for **Epever/EPSolar MPPT** solar charge controllers via Modbus RTU.

Replaces Node-RED with a single Docker stack: live web dashboard, REST API for settings control, Prometheus metrics, and a pre-built Grafana dashboard.

![Web UI](docs/screenshot-placeholder.png)

## Features

- **Web Dashboard** — real-time power flow, battery SOC gauge, energy stats, charge state
- **REST API** — read all registers, change any setting (voltages, battery type, load control)
- **Prometheus Metrics** — 29 gauges covering PV, battery, load, temperature, energy totals
- **Grafana Dashboard** — pre-provisioned with power overview, SOC history, charging state timeline
- **Swagger UI** — interactive API docs at `/docs`
- **Docker-ready** — one `docker compose up` gets everything running
- **Survives reboots** — stable `/dev/serial/by-id/` device paths, auto-restart

## Quick Start

### Prerequisites

- Raspberry Pi (or any Linux box) with USB connected to your Epever MPPT controller
- Docker and Docker Compose installed
- USB-to-RS485 adapter (Exar XR21B1411 tested, others should work)

### 1. Clone and configure

```bash
git clone https://github.com/mitchross/epever-solar-monitor.git
cd epever-solar-monitor
cp .env.example .env
```

Find your serial device:

```bash
ls /dev/serial/by-id/
# Example: usb-Exar_Corp._XR21B1411_Q2530014951-if00-port0
```

Edit `.env` and set `SERIAL_PORT` to your device path:

```env
SERIAL_PORT=/dev/serial/by-id/usb-Exar_Corp._XR21B1411_Q2530014951-if00-port0
```

### 2. Start everything

```bash
docker compose up -d
```

This starts three containers:

| Service | Port | URL |
|---------|------|-----|
| **Solar Monitor** (Web UI + API) | 8080 | `http://your-pi:8080` |
| **Prometheus** | 9090 | `http://your-pi:9090` |
| **Grafana** | 3000 | `http://your-pi:3000` (admin/solar) |

### 3. Open the dashboards

- **Web UI**: `http://your-pi:8080` — live power flow, readings, settings
- **Grafana**: `http://your-pi:3000` — time-series graphs, auto-provisioned solar dashboard
- **Swagger API**: `http://your-pi:8080/docs` — interactive API explorer

## Monitor Only (No Grafana/Prometheus)

If you already have Prometheus + Grafana elsewhere (e.g., a Kubernetes cluster), run just the monitor:

```bash
docker compose up -d epever-solar
```

Then point your Prometheus at `http://your-pi:9812/metrics`.

Import `grafana/dashboards/solar-dashboard-importable.json` into your Grafana.

## Hardware Setup

### Supported Controllers

Tested with **Epever Tracer AN/BN** series. Should work with any Epever controller that supports Modbus RTU over RS-485.

### Wiring

The controller connects via its **RJ45 RS-485 port** (not the MT-50 display port on some models):

| RJ45 Pin | Signal | Wire Color (T568B) |
|----------|--------|-------------------|
| 4 | RS-485 B (D-) | Blue |
| 6 | RS-485 A (D+) | Green |
| 8 | GND | Brown |

### USB Adapter

Tested with **Exar XR21B1411** USB-to-RS485 adapter. The `xr_serial` kernel module is built into Linux 6.5+. For older kernels, see the [epsolar-tracer](https://github.com/kasbert/epsolar-tracer) repo for the legacy driver.

### RS485 Notes

This adapter requires **RTS_AFTER_SEND** RS485 mode (not the more common RTS_ON_SEND). The monitor auto-configures this via kernel ioctl. If you use a different adapter and get no response, check `docs/rs485-troubleshooting.md`.

## API Reference

### Realtime Data

```bash
# Full status dump
curl http://localhost:8080/status

# Prometheus metrics
curl http://localhost:8080/metrics

# Health check
curl http://localhost:8080/health
```

### Settings

```bash
# Read all settings
curl http://localhost:8080/settings

# Change a setting
curl -X POST http://localhost:8080/settings/float_charging_voltage \
  -H "Content-Type: application/json" \
  -d '{"value": 13.6}'

# List all available registers
curl http://localhost:8080/registers
```

### Available Settings

**Charge Voltages**: `over_voltage_disconnect`, `charging_limit_voltage`, `over_voltage_reconnect`, `equalize_charging_voltage`, `boost_charging_voltage`, `float_charging_voltage`, `boost_reconnect_voltage`

**Discharge Voltages**: `low_voltage_reconnect`, `under_voltage_recover`, `under_voltage_warning`, `low_voltage_disconnect`, `discharging_limit_voltage`

**Battery**: `battery_type` (0=User, 1=Sealed, 2=GEL, 3=Flooded, 4=Lithium), `battery_capacity`, `temp_compensation_coeff`

**Load Control**: `manual_load_control`, `load_default_mode`, `enable_load_test`, `force_load`

> **Note**: Voltage registers (0x9003-0x900E) are batch-written automatically because Epever controllers reject individual voltage writes.

## LiFePO4 Battery Settings

If you're using LiFePO4 batteries, here are recommended settings:

| Setting | Value | Why |
|---------|-------|-----|
| `battery_type` | 0 (User) | Full manual control |
| `temp_compensation_coeff` | **0.0** | **Critical** — LiFePO4 has no temp-voltage relationship. Non-zero values cause dangerous overcharging in cold weather |
| `over_voltage_disconnect` | 15.0V | Emergency cutoff |
| `charging_limit_voltage` | 14.6V | 3.65V/cell max |
| `boost_charging_voltage` | 14.4V | Bulk charge target |
| `float_charging_voltage` | 13.6V | Maintenance |
| `low_voltage_disconnect` | 10.8V | 2.7V/cell safe floor |
| `discharging_limit_voltage` | 10.5V | Absolute minimum |

Apply via the API:

```bash
curl -X POST http://localhost:8080/settings/temp_compensation_coeff \
  -H "Content-Type: application/json" -d '{"value": 0.0}'
```

## Metrics Reference

All metrics are prefixed with `epever_`:

| Metric | Type | Description |
|--------|------|-------------|
| `epever_pv_voltage_volts` | gauge | Solar panel voltage |
| `epever_pv_power_watts` | gauge | Solar panel power |
| `epever_battery_voltage_volts` | gauge | Battery voltage |
| `epever_battery_soc_percent` | gauge | Battery state of charge |
| `epever_battery_charge_power_watts` | gauge | Battery charging power |
| `epever_load_power_watts` | gauge | Load power consumption |
| `epever_battery_temp_celsius` | gauge | Battery temperature |
| `epever_device_temp_celsius` | gauge | Controller temperature |
| `epever_generated_energy_today_kwh` | gauge | Energy generated today |
| `epever_generated_energy_total_kwh` | gauge | Lifetime energy generated |
| `epever_charging_state` | gauge | 0=off, 1=float, 2=boost, 3=equalize |
| ... and 18 more | | See `/registers` endpoint for full list |

## Architecture

```
┌─────────────────────────────────────────────┐
│  Docker Compose                             │
│                                             │
│  ┌───────────────────┐    ┌──────────────┐  │
│  │  epever-solar      │    │  Prometheus  │  │
│  │                    │◄───│  :9090       │  │
│  │  pymodbus + FastAPI│    └──────┬───────┘  │
│  │  :8080 (UI + API) │           │           │
│  │  :9812 (metrics)  │    ┌──────┴───────┐  │
│  └────────┬───────────┘    │  Grafana     │  │
│           │                │  :3000       │  │
│     ┌─────┴─────┐         └──────────────┘  │
│     │ /dev/ttyUSB│                           │
└─────┼────────────┼───────────────────────────┘
      │  RS-485    │
┌─────┴────────────┴─────┐
│  Epever MPPT Controller │
│  (Tracer AN/BN series)  │
└─────────────────────────┘
```

## Kubernetes Integration

If you run Prometheus + Grafana in a Kubernetes cluster, you only need the monitor container on the Pi.

**Prometheus scrape config** (`values.yaml`):

```yaml
additionalScrapeConfigs:
  - job_name: 'epever-solar'
    metrics_path: /metrics
    scheme: http
    scrape_interval: 15s
    static_configs:
      - targets: ['192.168.10.174:9812']
```

**Grafana dashboard**: Deploy `grafana/dashboards/solar-dashboard.json` as a ConfigMap with label `grafana_dashboard: "1"`.

**Network policy**: If using Cilium or Calico, whitelist your Pi's IP and port 9812 for egress from the Prometheus namespace.

## Troubleshooting

### No response from controller

1. **Check the cable** — RJ45 must be in the RS-485 port, not the MT-50 port
2. **Try both baud rates** — most Epever use 115200, some older models use 9600
3. **RS485 polarity** — some adapters need `RTS_ON_SEND`, others `RTS_AFTER_SEND`. The code defaults to `RTS_AFTER_SEND` for Exar chips. Edit `modbus_client.py` to flip if needed
4. **Check device exists**: `ls /dev/serial/by-id/`
5. **Check permissions**: user must be in the `dialout` group, or run with `privileged: true`

### Voltage settings won't write

Epever controllers reject individual voltage register writes (`exception code 4`). This monitor handles this automatically by batch-writing all 12 voltage registers together. If you still get errors, the value may be out of the controller's accepted range.

### Device path changes after reboot

Use `/dev/serial/by-id/...` instead of `/dev/ttyUSB0`. These are stable symlinks that don't change.

## Credits

- [kasbert/epsolar-tracer](https://github.com/kasbert/epsolar-tracer) — original Node.js implementation and RS485 driver work
- [pymodbus](https://github.com/pymodbus-dev/pymodbus) — Python Modbus library
- Built with [FastAPI](https://fastapi.tiangolo.com/), [Prometheus client](https://github.com/prometheus/client_python), [Grafana](https://grafana.com/)

## License

MIT
