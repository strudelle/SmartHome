# esp32_client.py - PC side: fetch the ESP32 reply and tell WHAT failed
#
#   ESP32Unreachable  -> no answer at all (ESP32 powered off, Wi-Fi down, wrong IP)
#   ESP32BadResponse  -> the ESP32 answered, but the reply is not what we expect
#   SensorFailure     -> the ESP32 is fine, one sensor (veml7700 / sht31) is not
import time
import requests

ESP32_URL = "http://10.0.0.66/"


class ESP32Error(Exception):
    """Base class for everything that can go wrong when reading the ESP32."""


class ESP32Unreachable(ESP32Error):
    """No answer from the ESP32."""


class ESP32BadResponse(ESP32Error):
    """The ESP32 answered with something unexpected."""


class SensorFailure(ESP32Error):
    """The ESP32 answered, but one of its sensors reported an error."""

    def __init__(self, sensor, message):
        super().__init__(f"{sensor} sensor failure: {message}")
        self.sensor = sensor
        self.message = message


def fetch(url=ESP32_URL, timeout=3, retries=2):
    """Return the parsed reply (dict). Raises ESP32Unreachable or ESP32BadResponse."""
    error = None
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(0.5)
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            payload = r.json()
        except (requests.ConnectionError, requests.Timeout) as e:
            error = ESP32Unreachable(
                f"No answer from ESP32 at {url} ({type(e).__name__}): "
                "powered off, Wi-Fi down or wrong IP?")
            continue
        except (requests.RequestException, ValueError) as e:
            error = ESP32BadResponse(f"Unexpected reply from ESP32 at {url}: {e}")
            continue

        if not isinstance(payload, dict) or not isinstance(payload.get("sensors"), dict):
            error = ESP32BadResponse(f"Unexpected JSON from ESP32 at {url}: {str(payload)[:100]}")
            continue
        return payload
    raise error


def sensor_data(payload, name):
    """Return one sensor's values (dict). Raises SensorFailure or ESP32BadResponse."""
    entry = payload["sensors"].get(name)
    if not isinstance(entry, dict):
        raise ESP32BadResponse(f"ESP32 reply has no '{name}' section")
    if not entry.get("ok"):
        raise SensorFailure(name, entry.get("error", "unknown error"))
    return entry
