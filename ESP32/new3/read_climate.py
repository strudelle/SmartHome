# read_climate.py - read the ESP32 once (or in a loop) and report each sensor's status
#
#   python read_climate.py         one reading
#   python read_climate.py loop    a reading every 30 s (Ctrl+C to stop)
#
# Exit code (single reading): 0 = all good, 1 = a sensor failed, 2 = ESP32 problem
import sys
import time
from esp32_client import ESP32Error, ESP32Unreachable, SensorFailure, fetch, sensor_data


def read_once():
    """Print one report and return the exit code."""
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        payload = fetch()
    except ESP32Unreachable as e:
        print(f"{stamp}  ESP32 UNREACHABLE - {e}")
        return 2
    except ESP32Error as e:
        print(f"{stamp}  ESP32 ERROR - {e}")
        return 2

    code = 0
    parts = []
    try:
        data = sensor_data(payload, "sht45")
        parts.append(f"temp={data['temp_c']:.1f} C  humidity={data['humidity']:.1f} %")
    except SensorFailure as e:
        parts.append(f"SHT45 ERROR ({e.message})")
        code = 1
    except ESP32Error as e:
        parts.append(f"ERROR ({e})")
        code = 2

    try:
        data = sensor_data(payload, "veml7700")
        parts.append(f"lux={data['lux']:.1f}")
    except SensorFailure as e:
        parts.append(f"VEML7700 ERROR ({e.message})")
        code = max(code, 1)
    except ESP32Error as e:
        parts.append(f"ERROR ({e})")
        code = 2

    print(f"{stamp}  " + "  |  ".join(parts))
    return code


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "loop":
        while True:
            read_once()
            time.sleep(30)
    else:
        sys.exit(read_once())
