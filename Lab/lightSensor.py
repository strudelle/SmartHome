
"""
Find IP adress and other information:
"C:\Program Files\Python310\python.exe" -m tinytuya scan


Tuya light sensor

Access ID/Client ID: xcfgrds39m7dswswgupg
Access Secret/Client Secret: 09fbf6fb994341a7a6788426f67c08f3
Project Code: p1762308455503uecyj9

LightSensor	eb5062e634ed4fe073yhja	Wifi小光照传感器(STC8G1K17+WBR3 BLE快连)	Online	Real Device	2025-11-04 20:56:15
gg-108695000128356227840

"""

# Example Usage of TinyTuya
import tinytuya
import time
import datetime
from libraries.util import LoggerSH
#d = tinytuya.Device('DEVICE_ID_HERE', 'IP_ADDRESS_HERE', 'LOCAL_KEY_HERE', version=3.3)

log = LoggerSH(to_console=True, log_file_name=f"lightSensorTuya.txt")
run = True
delay = 2


d = tinytuya.Device('eb5062e634ed4fe073yhja', '10.0.0.190', 'ERq&*q]fyx*!s/]n', version=3.4)
data = d.status()
lum = data['dps']['7']

lum_str = str(int(lum)).rjust(4)
message = f"Lum:{lum_str}"
curve = (int((lum / 2)) * " ") + "*"
log.log_message(f"{message} {curve}")

while run:
    lum_list = []
    for i in range(0, 5):
        try:
            d = tinytuya.Device('eb5062e634ed4fe073yhja', '10.0.0.190', 'ERq&*q]fyx*!s/]n', version=3.4)
            data = d.status()
            lum = data['dps']['7']
            lum_list.append(lum)
        except Exception as err:
            error_message = f"{Exception=}, {err=}"
            log.log_message(f"{error_message=}")
        time.sleep(delay)
    avg_lum = 0
    for lum in lum_list:
        avg_lum += lum
    if len(lum_list):
        avg_lum = avg_lum / len(lum_list)
        lum_str = str(int(avg_lum)).rjust(4)
        message = f"Lum:{lum_str}"
        curve = (int((avg_lum/2)) * " ") + "*"
    else:
        message = f"Lum:  NA"
        curve = ""
    log.log_message(f"{message} {curve}")

