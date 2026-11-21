# main.py
import network
import socket
import time
import json
from machine import Pin, I2C
from veml7700 import VEML7700
from sht31 import SHT31
from wifi_config import SSID, PASSWORD

# --- Sensors ---
i2c = I2C(0, sda=Pin(21), scl=Pin(22), freq=100000)
devices = i2c.scan()
print("I2C devices:", [hex(a) for a in devices])  # expect 0x10 (VEML7700) and 0x44 (SHT31)

sensor = VEML7700(i2c)

try:
    sht = SHT31(i2c, addr=0x44)
except OSError as e:
    print("SHT31 init failed:", e)
    sht = None

# --- Wi-Fi ---
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.config(pm=network.WLAN.PM_NONE)  # more responsive, less latency
    if not wlan.isconnected():
        wlan.connect(SSID, PASSWORD)
        t = time.time()
        while not wlan.isconnected():
            if time.time() - t > 20:
                raise RuntimeError("Wi-Fi connection failed")
            time.sleep(0.5)
    print("Connected:", wlan.ifconfig())
    return wlan

wlan = connect_wifi()

# --- HTTP server ---
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("0.0.0.0", 80))
s.listen(2)
s.settimeout(5)
print("Server ready on port 80")


def read_sht():
    """Return (temp_c, humidity) or (None, None) if the SHT31 fails."""
    if sht is None:
        return None, None
    try:
        t, h = sht.read()
        return round(t, 2), round(h, 2)
    except (OSError, ValueError) as e:
        print("SHT31 error:", e)
        return None, None


while True:
    # Reconnect if Wi-Fi dropped
    if not wlan.isconnected():
        try:
            wlan = connect_wifi()
        except RuntimeError:
            time.sleep(10)
            continue

    try:
        conn, addr = s.accept()
    except OSError:
        continue  # timeout, loop again

    try:
        conn.settimeout(3)
        conn.recv(1024)  # we don't care about the request details
        lux = sensor.read_lux()
        temp_c, humidity = read_sht()
        body = json.dumps({
            "lux": round(lux, 2),
            "raw": sensor.last_raw,
            "gain": sensor.gain,
            "it": sensor.it,
            "temp_c": temp_c,
            "humidity": humidity,
        })
        conn.send(
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            "Connection: close\r\n\r\n" + body
        )
    except Exception as e:
        print("Error:", e)
    finally:
        conn.close()