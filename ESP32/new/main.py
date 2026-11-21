# main.py - ESP32 sensor server (MicroPython)
#
# GET http://<esp32-ip>/ returns JSON like:
#   {"ok": false, "uptime_s": 1234,
#    "sensors": {"veml7700": {"ok": true,  "lux": 123.4, "raw": 3428, "gain": "2", "it": 800},
#                "sht31":    {"ok": false, "error": "sht31 not found on I2C bus at 0x44"}}}
# If the ESP32 is alive, it always answers; a failing sensor only affects its own section.
import network
import socket
import time
import json
from machine import Pin, I2C
from sensor_base import SensorError
from veml7700 import VEML7700
from sht31 import SHT31
from wifi_config import SSID, PASSWORD

PORT = 80
BOOT_TIME = time.time()

# --- I2C bus ---
i2c = I2C(0, sda=Pin(21), scl=Pin(22), freq=100000)
print("I2C devices:", [hex(a) for a in i2c.scan()])  # expect 0x10 (VEML7700) and 0x44 (SHT31)


class SensorSlot:
    """Holds one sensor, (re)initialises it when needed, and never raises on read."""

    def __init__(self, i2c, driver, **options):
        self.i2c = i2c
        self.driver = driver
        self.options = options
        self.name = driver.NAME
        self.sensor = None

    def read(self):
        """Return {"ok": True, ...values} or {"ok": False, "error": "..."}."""
        try:
            if self.sensor is None:
                self.sensor = self.driver(self.i2c, **self.options)
            result = self.sensor.read()
            result["ok"] = True
            return result
        except Exception as e:
            self.sensor = None            # force a fresh init on the next request
            if isinstance(e, SensorError):
                message = str(e)
            else:
                message = "%s: %s" % (type(e).__name__, e)
            return {"ok": False, "error": message}


# One line per sensor, same pattern for all of them
SLOTS = (
    SensorSlot(i2c, VEML7700),
    SensorSlot(i2c, SHT31),
)


def read_all():
    sensors = {}
    for slot in SLOTS:
        sensors[slot.name] = slot.read()
    return {
        "ok": all(s["ok"] for s in sensors.values()),
        "uptime_s": time.time() - BOOT_TIME,
        "sensors": sensors,
    }


# --- Wi-Fi ---
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.config(pm=network.WLAN.PM_NONE)  # more responsive, less latency
    if not wlan.isconnected():
        wlan.connect(SSID, PASSWORD)
        start = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), start) > 20000:
                raise RuntimeError("Wi-Fi connection failed")
            time.sleep(0.5)
    print("Connected:", wlan.ifconfig())
    return wlan


# --- HTTP server ---
def start_server():
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", PORT))
    server.listen(2)
    server.settimeout(5)
    print("Server ready on port", PORT)
    return server


def handle_client(conn):
    conn.settimeout(3)
    conn.recv(1024)  # we don't care about the request details
    body = json.dumps(read_all())
    conn.send(
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: application/json\r\n"
        "Connection: close\r\n\r\n" + body
    )


def main():
    # Boot self-test: shows in the console which sensors are healthy
    for slot in SLOTS:
        print(slot.name, slot.read())

    wlan = None
    while wlan is None:
        try:
            wlan = connect_wifi()
        except RuntimeError as e:
            print(e)
            time.sleep(10)

    server = start_server()

    while True:
        # Reconnect if Wi-Fi dropped
        if not wlan.isconnected():
            try:
                wlan = connect_wifi()
            except RuntimeError as e:
                print(e)
                time.sleep(10)
                continue

        try:
            conn, addr = server.accept()
        except OSError:
            continue  # timeout, loop again

        try:
            handle_client(conn)  # This is where the data is sent
        except Exception as e:
            print("Error:", e)
        finally:
            conn.close()


main()
