import time
import requests
from libraries.util import LoggerSH

ESP32_URL = "http://10.0.0.66/"


def get_lux(timeout=3, retries=2):
    """Return ambient light in lux, or None if the sensor is unreachable."""
    for _ in range(retries + 1):
        try:
            r = requests.get(ESP32_URL, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, KeyError, ValueError):
            print("ERROR reading Lux")
            time.sleep(0.5)
    return None


class LightMonitor:
    """Smooths readings and adds hysteresis to avoid flickering decisions."""

    def __init__(self, dark_below=50, bright_above=150, samples=12):
        self.dark_below = dark_below
        self.bright_above = bright_above
        self.samples = samples
        self.history = []
        self.is_dark = False

    def update(self):
        lux_json = get_lux()
        if lux_json is None:
            return self.is_dark, None, {}  # keep last state if sensor is down
        lux = lux_json["lux"]
        self.history = (self.history + [lux])[-self.samples:]
        avg = sum(self.history) / len(self.history)

        if not self.is_dark and avg < self.dark_below:
            self.is_dark = True
        elif self.is_dark and avg > self.bright_above:
            self.is_dark = False
        return self.is_dark, avg, lux_json


# Example usage in your automation loop
monitor = LightMonitor(dark_below=50, bright_above=150)
log = LoggerSH(to_console=True, log_file_name=f"lightSensorESP32.txt")

while True:
    is_dark, lux, raw_json = monitor.update()
    if lux is None:
        lux_str = "-"
        curve = ""
    else:
        lux_str = f"{lux:.2f}".rjust(6)
        curve = (int((lux / 4)) * " ") + "*"
    log.log_message(f"lux={lux_str} h={raw_json['humidity']:.2f} t={raw_json['temp_c']:.2f} {curve}")
    # if is_dark and someone_home: turn_on_lights()
    time.sleep(60)

