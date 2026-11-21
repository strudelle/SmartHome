from threading import Thread, Lock
import datetime
import requests
from libraries.util import LoggerSH
import time
import json
import tinytuya


class LightSensor(Thread):
    def __init__(self, device_id, ip_address, local_key, module_enable=True):
        Thread.__init__(self)
        self.module_enable = module_enable
        self.class_name = self.__class__.__name__
        print(f'Init: {self.class_name}, Module:{"Enable" if module_enable else "Disabled"}')
        self.__log_lk = LoggerSH(heart_beat_delay=120, to_console=False,
                                 log_file_name=f"{self.class_name}_err.txt")

        self.__throttle_delay = 15  # delay between sample (sec)
        self.__average_over_min = 3  # will do the average over 2 minutes
        self.__total_sample = round(self.__average_over_min * 60 / self.__throttle_delay)
        self.__next_query = time.monotonic()
        self.stop_thread = False
        self.main_alive = time.monotonic()
        self.main_request = time.monotonic()

        # Class specific variable
        self.device_id = device_id
        self.ip_address = ip_address
        self.local_key = local_key
        self.version = 3.4

        # Variable to be protected by the lock
        self.lock_access = Lock()
        self.luminosity_data = []
        self.avg_luminosity = -1

    def run(self):
        self.__log_lk.log_message(f"Start: {self.class_name}")
        while not self.stop_thread:
            with self.lock_access:
                self.__log_lk.log_alive()
            if time.monotonic() >= self.__next_query:
                self.__next_query = time.monotonic() + self.__throttle_delay
                if self.module_enable:
                    try:
                        light_sensor = tinytuya.Device('eb5062e634ed4fe073yhja', '10.0.0.190', 'ERq&*q]fyx*!s/]n', version=3.4)
                        data = light_sensor.status()
                        lum = data['dps']['7']
                        with self.lock_access:
                            self.luminosity_data.append(lum)
                            if len(self.luminosity_data) > self.__total_sample:
                                self.luminosity_data.pop(0)
                            total = 0
                            for value in self.luminosity_data:
                                total += value
                            self.avg_luminosity = round(total / len(self.luminosity_data))
                            self.__log_lk.log_message(f"{self.avg_luminosity} - {self.luminosity_data}")
                    except Exception as err:
                        error_message = f"{Exception=}, {err=}"
                        with self.lock_access:
                            self.__log_lk.log_message(f"{error_message=}")
            time.sleep(0.1)
            if time.monotonic() >= self.main_alive + 1000:
                self.__log_lk.log_message("Main thread seems to be dead")
                self.stop_thread = True
        print(f"Ending thread {self.class_name}")
        with self.lock_access:
            self.__log_lk.log_message(f"Exited: {self.class_name}")

    def get_state(self):
        with self.lock_access:
            state = self.avg_luminosity
            self.main_alive = time.monotonic()
        return state

def main():
    log = LoggerSH(to_console=True, log_file_name=f"lightSensorTuya.txt")
    light_sensor = LightSensor('eb5062e634ed4fe073yhja', '10.0.0.190', 'ERq&*q]fyx*!s/]n')
    light_sensor.start()
    continue_to_run = True
    luminosity = -1
    while luminosity == -1:
        luminosity = light_sensor.get_state()
        time.sleep(1)
    while continue_to_run:
        luminosity = light_sensor.get_state()
        lum_str = str(int(luminosity)).rjust(4)
        message = f"Lum:{lum_str}"
        curve = (int((luminosity/4)) * " ") + "*"
        log.log_message(f"{message} {curve}")
        time.sleep(60)


if __name__ == '__main__':
    main()
