FROM python:3.13-slim

# Install D-Bus and Bluetooth libraries for BLE support
RUN apt-get update && apt-get install -y --no-install-recommends \
    libdbus-1-dev libglib2.0-dev bluez && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY epever_monitor/ ./epever_monitor/

EXPOSE 8080 9812

CMD ["uvicorn", "epever_monitor.main:app", "--host", "0.0.0.0", "--port", "8080"]
