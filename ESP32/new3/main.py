# main.py - ESP32 sensor server (MicroPython)
#
# GET http://<esp32-ip>/ returns JSON like:
#   {"ok": true,
#    "sensors": {"veml7700": {"ok": true, "lux": 123.4, "raw": 3428, "gain": "2", "it": 800},
#                "sht45":    {"ok": true, "temp_c": 22.1, "humidity": 48.3}},
#    "device":  {"uptime_s": 86400, "reset_cause": "power_on", "mem_free": 81234,
#                "mem_alloc": 18432, "rssi": -61, "requests": 1440, "wifi_reconnects": 0}}
#
# Self-recovery: a hardware watchdog reboots the board if the main loop gets stuck,
# and the board reboots by itself if nobody has been served for NO_CLIENT_REBOOT_S.
import errno
import gc
import json
import machine
import network
import socket
import time
from machine import Pin, I2C, WDT
from sensor_base import SensorError
from veml7700 import VEML7700
from sht45 import SHT45
from wifi_config import SSID, PASSWORD

PORT = 80
WDT_TIMEOUT_MS = 120000          # reboot if the main loop is stuck for 2 minutes
NO_CLIENT_REBOOT_S = 900         # reboot if no client was served for 15 min (None = never)
MAX_CONSECUTIVE_ERRORS = 20      # reboot after this many failed loop iterations in a row
BOOT_TIME = time.time()

_RESET_NAMES = {
    machine.PWRON_RESET: "power_on",
    machine.HARD_RESET: "hard_reset",
    machine.WDT_RESET: "watchdog",
    machine.DEEPSLEEP_RESET: "deep_sleep",
    machine.SOFT_RESET: "soft_reset",
}
RESET_CAUSE = _RESET_NAMES.get(machine.reset_cause(), "unknown")
stats = {"requests": 0, "wifi_reconnects": 0}

# --- I2C bus ---
i2c = I2C(0, sda=Pin(21), scl=Pin(22), freq=100000)
elapse_top = int(time.time() - BOOT_TIME)
print(elapse_top, " - Reset cause:", RESET_CAUSE)
print(elapse_top, " - I2C devices:", [hex(a) for a in i2c.scan()])  # expect 0x10 (VEML7700) and 0x44 (SHT45)


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
    SensorSlot(i2c, SHT45, addr=0x44),
)


def read_all():
    sensors = {}
    for slot in SLOTS:
        sensors[slot.name] = slot.read()
    return {"ok": all(s["ok"] for s in sensors.values()), "sensors": sensors}


def device_info(wlan):
    """Health numbers of the board itself; watch mem_free over days to spot a leak."""
    gc.collect()
    try:
        rssi = wlan.status("rssi")
    except Exception:
        rssi = None
    return {
        "uptime_s": time.time() - BOOT_TIME,
        "reset_cause": RESET_CAUSE,
        "mem_free": gc.mem_free(),
        "mem_alloc": gc.mem_alloc(),
        "rssi": rssi,
        "requests": stats["requests"],
        "wifi_reconnects": stats["wifi_reconnects"],
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
    elapse = int(time.time() - BOOT_TIME)
    print(elapse, " - Connected:", wlan.ifconfig())
    return wlan


# --- HTTP server ---
def start_server():
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", PORT))
    server.listen(2)
    server.settimeout(5)
    elapse = int(time.time() - BOOT_TIME)
    print(elapse, " - Server ready on port", PORT)
    return server


def handle_client(conn, wlan):
    conn.settimeout(3)
    conn.recv(1024)  # we don't care about the request details
    payload = read_all()
    payload["device"] = device_info(wlan)
    body = json.dumps(payload)
    conn.send(
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: application/json\r\n"
        "Connection: close\r\n\r\n" + body
    )


def is_timeout(e):
    return bool(e.args) and e.args[0] in (errno.ETIMEDOUT, errno.EAGAIN)


def main():
    wdt = WDT(timeout=WDT_TIMEOUT_MS)

    # Boot self-test: shows in the console which sensors are healthy
    elapse = int(time.time() - BOOT_TIME)
    print(elapse, "Init Sensor")
    for slot in SLOTS:
        print(slot.name, slot.read())

    wlan = None
    server = None
    last_served = time.time()
    errors = 0

    while True:
        wdt.feed()

        if NO_CLIENT_REBOOT_S and time.time() - last_served > NO_CLIENT_REBOOT_S:
            elapse = int(time.time() - BOOT_TIME)
            print(elapse, " - No client served for %d s, rebooting" % NO_CLIENT_REBOOT_S)
            machine.reset()

        try:
            # (Re)connect Wi-Fi; any failure is handled below, never fatal
            if wlan is None or not wlan.isconnected():
                if wlan is not None:
                    stats["wifi_reconnects"] += 1
                wlan = connect_wifi()
            if server is None:
                server = start_server()

            try:
                conn, addr = server.accept()
            except OSError as e:
                if not is_timeout(e):
                    raise                 # a real socket problem, not just "nobody called"
                conn = None

            if conn is not None:
                try:
                    handle_client(conn, wlan)
                    stats["requests"] += 1
                    last_served = time.time()
                except OSError as e:
                    # Client-side problem (connected but sent nothing, dropped mid-reply):
                    # log it and keep the server socket
                    elapse = int(time.time() - BOOT_TIME)
                    print(elapse, " - Client error:", repr(e))
                finally:
                    conn.close()
            errors = 0

        except Exception as e:
            errors += 1
            print(elapse, " - Error (%d in a row): %r" % (errors, e))
            elapse = int(time.time() - BOOT_TIME)
            if errors >= MAX_CONSECUTIVE_ERRORS:
                elapse = int(time.time() - BOOT_TIME)
                print(elapse, " - Too many errors, rebooting")
                machine.reset()
            try:
                if server is not None:
                    server.close()
            except Exception:
                pass
            server = None                 # rebuilt on the next iteration
            time.sleep(5)


main()
