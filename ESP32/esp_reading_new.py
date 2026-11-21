import time
import requests
from libraries.util import LoggerSH

ESP32_URL = "http://10.0.0.66/"


def esp32_request(timeout=5, retries=3):
    """Return ambient light in lux, or None if the sensor is unreachable."""
    r_error = {'ok': False,
               'sensors': {
                   'sht45': {'humidity': 0.0, 'temp_c': 0, 'ok': False},
                   'veml7700': {'raw': 0, 'gain': '0', 'it': 0, 'lux': 0, 'ok': False}},
               'device': {'mem_free': 0,
                          'uptime_s': 0,
                          'reset_cause': '-',
                          'mem_alloc': 0,
                          'rssi': 0,
                          'wifi_reconnects': 0,
                          'requests': 0}
               }
    for _ in range(retries + 1):
        try:
            r = requests.get(ESP32_URL, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, KeyError, ValueError):
            print("ERROR esp32 unreachable")
            time.sleep(0.5)
    return r_error


class EnvironmentMonitor:
    """Smooths readings and adds hysteresis to avoid flickering decisions."""

    def __init__(self, samples=12):
        self.samples = samples
        self.lux_history = []

    def read_data(self):
        esp32_data = esp32_request()
        if esp32_data['sensors']['veml7700']['ok']:
            lux = esp32_data['sensors']['veml7700']['lux']
            self.lux_history = (self.lux_history + [lux])[-self.samples:]
            lux_avg = sum(self.lux_history) / len(self.lux_history)
        else:
            lux_avg = None
        if esp32_data['sensors']['sht45']['ok']:
            temperature = esp32_data['sensors']['sht45']['temp_c']
            humidity = esp32_data['sensors']['sht45']['humidity']
        else:
            temperature = None
            humidity = None
        return lux_avg, temperature, humidity, esp32_data


# Example usage in your automation loop
monitor = EnvironmentMonitor()
log = LoggerSH(to_console=True, log_file_name=f"SensorESP32.txt")
prev_uptime = 0
delay = 60
start_time = time.monotonic()
loop_count = 0
while True:
    loop_count += 1
    lux_avg, temperature, humidity, raw_json = monitor.read_data()
    device = raw_json['device']
    uptime = device['uptime_s']
    if uptime != 0:
        if uptime < prev_uptime:
            log.log_message(f"ERROR ESP32 Rebooted uptime now: {uptime} previous: {prev_uptime}")
        prev_uptime = uptime
    if lux_avg is None:
        lux_avg_str = "     -"
        curve = ""
        extra = "(      )"
    else:
        lux_avg_str = f"{lux_avg:.2f}".rjust(6)
        lux_ins_str = f"{raw_json['sensors']['veml7700']['lux']:.2f}".rjust(6)
        raw = f"{raw_json['sensors']['veml7700']['raw']}".rjust(6)
        gain = f"{raw_json['sensors']['veml7700']['gain']}".rjust(2)
        it = f"{raw_json['sensors']['veml7700']['it']}".rjust(4)
        extra = f"({lux_ins_str}{raw}{gain}{it})"
        curve = (int((lux_avg / 4)) * " ") + "*"

    if temperature is None:
        temperature_str = '--.--'
    else:
        temperature_str = f"{temperature:.1f}"

    if humidity is None:
        humidity_str = '--.--'
    else:
        humidity_str = f"{humidity:.2f}"

    # device_str = f"esp32[up={uptime / 3600:3.1f}h/{uptime}s " \
    #              f"m_free={device.get('mem_free')} m_alloc={device.get('mem_alloc')}" \
    #              f" rssi={device.get('rssi')} reset={device.get('reset_cause')}" \
    #              f" reconnects={device.get('wifi_reconnects')} request={device.get('requests')}]"
    device_str = f"esp32[up={uptime / 3600:7.1f}h/{uptime:7d}s " \
                 f"m_free={device.get('mem_free'):6d} m_alloc={device.get('mem_alloc'):6d}" \
                 f" rssi={device.get('rssi'):3d} reset={str(device.get('reset_cause')):>10}" \
                 f" reconnects={device.get('wifi_reconnects'):3d} request={device.get('requests'):6d}]"

    log.log_message(f"lux={lux_avg_str} h={humidity_str} t={temperature_str} {extra} {device_str} {curve}")
    time.sleep((delay * loop_count) - (time.monotonic() - start_time))

