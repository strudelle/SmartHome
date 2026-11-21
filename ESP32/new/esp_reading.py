# esp_reading.py - automation loop: light level with hysteresis + temperature/humidity
import time
from libraries.util import LoggerSH
from esp32_client import ESP32Error, fetch, sensor_data


class LightMonitor:
    """Smooths readings and adds hysteresis to avoid flickering decisions."""

    def __init__(self, dark_below=50, bright_above=150, samples=12):
        self.dark_below = dark_below
        self.bright_above = bright_above
        self.samples = samples
        self.history = []
        self.is_dark = False

    def update(self, payload):
        """Feed one ESP32 reply. Returns (is_dark, avg_lux, error).

        If the light sensor can't be read, the previous state is kept,
        avg_lux is None and error explains why (SensorFailure, ESP32BadResponse...).
        """
        try:
            lux = sensor_data(payload, "veml7700")["lux"]
        except ESP32Error as e:
            return self.is_dark, None, e

        self.history = (self.history + [lux])[-self.samples:]
        avg = sum(self.history) / len(self.history)

        if not self.is_dark and avg < self.dark_below:
            self.is_dark = True
        elif self.is_dark and avg > self.bright_above:
            self.is_dark = False
        return self.is_dark, avg, None


def main():
    monitor = LightMonitor(dark_below=50, bright_above=150)
    log = LoggerSH(to_console=True, log_file_name="lightSensorESP32.txt")

    while True:
        try:
            payload = fetch()
        except ESP32Error as e:                   # ESP32 down / unusable reply
            log.log_message(f"ESP32 ERROR: {e}")
            time.sleep(60)
            continue

        is_dark, lux, light_error = monitor.update(payload)
        if light_error is None:
            light_str = f"lux={lux:.2f}, dark={is_dark}"
        else:
            light_str = f"light ERROR ({light_error}), dark={is_dark}"

        try:
            climate = sensor_data(payload, "sht31")
            climate_str = f"temp={climate['temp_c']}C, humidity={climate['humidity']}%"
        except ESP32Error as e:
            climate_str = f"climate ERROR ({e})"

        log.log_message(f"{light_str}, {climate_str}")
        # if is_dark and someone_home: turn_on_lights()
        time.sleep(60)


if __name__ == "__main__":
    main()
