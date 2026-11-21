# main.py
import network
import socket
import time
import json
from machine import Pin, I2C
from veml7700 import VEML7700

SSID = "TruHome"
PASSWORD = "Mathieu20Leanne12"

# --- Sensor ---
i2c = I2C(0, sda=Pin(21), scl=Pin(22), freq=100000)
print("I2C devices:", [hex(a) for a in i2c.scan()])  # should show 0x10
sensor = VEML7700(i2c)

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
        body = json.dumps({"lux": round(lux, 2), "raw": sensor.last_raw, "gain": sensor.gain, "it": sensor.it})
        conn.send(
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            "Connection: close\r\n\r\n" + body
        )
    except Exception as e:
        print("Error:", e)
    finally:
        conn.close()