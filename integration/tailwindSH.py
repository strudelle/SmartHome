from threading import Thread, Lock
import datetime
import requests
from libraries.util import LoggerSH
import time
import json
import keyring


class TailwindIQ3Integration(Thread):
    def __init__(self, token=None, ip=None, mac=None, module_enable=True):
        Thread.__init__(self)
        self.module_enable = module_enable
        print(f'Init: {self.__class__.__name__}, Module:{"Enable" if module_enable else "Disabled"}')
        self.__log_lk = LoggerSH(heart_beat_delay=120, to_console=False, log_file_name=f"{self.__class__.__name__}_err.txt")
        self._token = token if token else keyring.get_password("tailwind", "token")
        if ip:
            self.url = f"http://{ip}/json"
        else:
            self.url = f"http://tailwind-{mac}.local/json"
        self.headers = {'Content-Type': 'application/json', 'TOKEN': self._token}
        self.version = "0.1"

        self.__throttle_delay = 1
        self.__next_query = time.monotonic() + self.__throttle_delay
        self.run_thread = True

        self.closing_max_delay = 45
        self.opening_max_delay = 30

        self.main_alive = time.monotonic()


        # Variable to be protected by the lock
        self.lock_access = Lock()
        self.door_name_to_activate_lk = ""
        self.garage_door_state_lk = {}
        self.need_to_close_the_door_lk = False
        self.closing_timer_start_lk = 0
        self.need_to_open_the_door_lk = False
        self.opening_timer_start_lk = 0

        # initialize some other variables... this includes updating garage_door_state_lk
        self._door_index = self._load_door_index()
        self.start_time = datetime.datetime.now()

    def run(self):
        self.__log_lk.log_message(f"Start: run_iq3")
        while self.run_thread:
            with self.lock_access:
                self.__log_lk.log_alive()
            if time.monotonic() >= self.__next_query:
                self.__next_query = time.monotonic() + self.__throttle_delay
                if self.module_enable:
                    self._get_garage_door_state()
                    # Check if we need to Open/Close the door
                    with self.lock_access:
                        will_open = self.need_to_open_the_door_lk
                        will_close = self.need_to_close_the_door_lk
                        door_name = self.door_name_to_activate_lk

                    # Close the garage Door
                    if will_close:
                        with self.lock_access:
                            self.__log_lk.log_message("Will Close the door")
                        status = self._activate_door(door_name, "close")
                        if status['result'] == "OK":
                            with self.lock_access:
                                self.need_to_close_the_door_lk = False

                    # Open the garage Door
                    if will_open:
                        with self.lock_access:
                            self.__log_lk.log_message("Will Open the door")
                        status = self._activate_door(door_name, "open")
                        if status['result'] == "OK":
                            with self.lock_access:
                                self.need_to_open_the_door_lk = False
                else:
                    with self.lock_access:
                        self.garage_door_state_lk['door1'] = {
                            'index': 0,
                            "state": "close",
                            "last_update": self.start_time,
                            "last_health": datetime.datetime.now()
                        }
            time.sleep(.1)
        print("Ending thread iq3")
        with self.lock_access:
            self.__log_lk.log_message("Exited: run_iq3")

    def close(self, door_name):
        if not self.module_enable:
            return
        with self.lock_access:
            self.need_to_close_the_door_lk = True
            self.door_name_to_activate_lk = door_name
            self.closing_timer_start_lk = time.monotonic()

    def open(self, door_name):
        if not self.module_enable:
            return
        with self.lock_access:
            self.need_to_open_the_door_lk = True
            self.door_name_to_activate_lk = door_name
            self.opening_timer_start_lk = time.monotonic()

    def get_state(self):
        with self.lock_access:
            state = self.garage_door_state_lk
            self.main_alive = time.monotonic()
        return state

    def _activate_door(self, door_name, action):
        data = {
            "type": "set",
            "name": "door_op",
            'value':
                {"door_idx": self._door_index[door_name],
                 "cmd": action}}
        body = {'product': 'iQ3', 'version': self.version, 'data': data}
        response_text = self.__send_request(body)
        if response_text != "":
            status = json.loads(response_text)
        else:
            status = {'result': 'ERROR'}
        return status

    def _load_door_index(self):
        self._get_garage_door_state()
        door_index = {}
        with self.lock_access:
            for door in self.garage_door_state_lk.keys():
                door_index[door] = self.garage_door_state_lk[door]['index']
        return door_index

    def _get_garage_door_state(self):
        """
        Return if door name is not specify, return a dictionary containing the door status of each door,
        if door name is specified, just return the state as open or close
        :return:
        """
        data = {
            "type": "get",
            "name": "dev_st"}
        body = {'version': self.version, 'data': data}
        response_text = self.__send_request(body)
        if response_text != "":
            device_status = json.loads(response_text)
            door_data = device_status['data']
            for door in door_data.keys():
                door_data[door]['state'] = door_data[door].pop('status')
                door_data[door]['last_health'] = datetime.datetime.now()
                with self.lock_access:
                    if self.garage_door_state_lk == {} or door_data[door]['state'] != self.garage_door_state_lk[door]['state']:
                        door_data[door]['last_update'] = datetime.datetime.now()
                    else:
                        door_data[door]['last_update'] = self.garage_door_state_lk[door]['last_update']
        # else:
        #     door_data = {'door1': {
        #         'index': 0,
        #         "state": "close",
        #         "last_update": datetime.datetime.now()
        #     }}
            with self.lock_access:
                self.garage_door_state_lk = door_data

    def __send_request(self, body):
        response_text = ""
        try:
            response = requests.post(self.url, headers=self.headers, json=body)
            if response.status_code == 200:
                response_text = response.text
            else:
                error_message = f"Error: {response.status_code} {response.reason} body={body}"
                with self.lock_access:
                    self.__log_lk.log_message(error_message)
        except Exception as err:
            error_message = f"{Exception=}, {err=} body={body}"
            with self.lock_access:
                self.__log_lk.log_message(error_message)
            # Something did go wrong, we will gve it a break... and do next query only in 1 minutes
            self.__next_query = time.monotonic() + 60
        return response_text


def main():
    iq3 = TailwindIQ3Integration(keyring.get_password("tailwind", "token"), ip="10.0.0.158", module_enable=True)
    iq3.start()

    garage_devices = iq3.get_state()
    state = garage_devices['door1']['state']
    last_update = garage_devices['door1']['last_update']
    print(f"Initial Door State: {state} {last_update}")

    print("Will monitor things 5 seconds")
    for i in range(0, 5):
        time.sleep(1)
        garage_devices = iq3.get_state()
        state = garage_devices['door1']['state']
        last_update = garage_devices['door1']['last_update']
        last_health = garage_devices['door1']['last_health']
        print(f"{i}:{state} {last_update}, {last_health}")

    print("Request to Open Door")
    iq3.open("door1")

    duration = 30
    print(f"Will monitor things {duration} seconds")
    for i in range(0, duration):
        garage_devices = iq3.get_state()
        state = garage_devices['door1']['state']
        last_update = garage_devices['door1']['last_update']
        print(f"{i}:{state} {last_update}")
        time.sleep(1)

    print("Request to Close Door")
    iq3.close("door1")

    print(f"Will monitor things {duration} seconds")
    for i in range(0, duration):
        garage_devices = iq3.get_state()
        state = garage_devices['door1']['state']
        last_update = garage_devices['door1']['last_update']
        print(f"{i}:{state} {last_update}")
        time.sleep(1)

    iq3.run_thread = False

    print("Done")


def monitor():
    iq3 = TailwindIQ3Integration(keyring.get_password("tailwind", "token"), ip="10.0.0.158", module_enable=False)
    iq3.start()

    garage_devices = iq3.get_state()
    state = garage_devices['door1']['state']
    last_update = garage_devices['door1']['last_update']
    print(f"Initial Door State: {state} {last_update}")
    previous_state = state

    while True:
        state = garage_devices['door1']['state']
        last_update = garage_devices['door1']['last_update']
        if state != previous_state:
            print(f"Porte de Garage:{state} {last_update}")
        previous_state = state
        time.sleep(1)


if __name__ == '__main__':
    main()
