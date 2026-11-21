import asyncio
import time
from libraries.util import LoggerSH
from aiohttp import ClientSession
from threading import Thread, Lock
import pymyq
import datetime
import inspect
import os
import keyring


class MyQIntegration(Thread):
    def __init__(self, username, device_id, module_enable=True, password=None):
        Thread.__init__(self)
        self.module_enable = module_enable
        print(f'Init: {self.__class__.__name__}, Module:{"Enable" if module_enable else "Disabled"}')
        self.__log = LoggerSH(heart_beat_delay=120, to_console=False, log_file_name=f"{self.__class__.__name__}_err.txt")
        self.username = username
        self.password = password if password else keyring.get_password("myq", username)
        self.device_id = device_id
        self.__throttle_delay = 10
        self.__next_query = time.monotonic()
        self.loop_myq = True
        self.lock_access = Lock()
        self.garage_state = {}
        self.need_to_close_the_door = False
        self.closing_max_delay = 45
        self.closing_timer_start = 0
        self.need_to_open_the_door = False
        self.opening_max_delay = 30
        self.opening_timer_start = 0
        self.main_alive = time.monotonic()


    def run(self):
        if os.name == 'nt':  # nt = windows, posix = linux
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        while self.loop_myq is True:
            asyncio.run(self._run_myq())
            self.__log.log_message("Exited: run_myq")

    async def _run_myq(self):
        self.__log.log_message(f"Start: run_myq")
        async with ClientSession() as web_session:
            if self.module_enable:
                try:
                    myq = await pymyq.login(self.username, self.password, web_session)
                except Exception as err:
                    function = inspect.stack()[0].function
                    error_message = f"{function=}, {Exception=}, {err=}"
                    self.__log.log_message(error_message)

                devices = myq.covers
                device = devices[self.device_id]
                state = device.state.upper()
                with self.lock_access:
                    self.garage_state[device.name] = {
                        "state": state,
                        "last_update": datetime.datetime.now()
                    }
                reset_myq = False
                while self.loop_myq:
                    self.__log.log_alive()
                    # Monitor the state of the door and update the state if it changed
                    if time.monotonic() >= self.__next_query:
                        self.__next_query = time.monotonic() + self.__throttle_delay
                        previous_state = state
                        try:
                            await device.update()
                        except Exception as err:
                            function = inspect.stack()[0].function
                            error_message = f"{function=}, {Exception=}, {err=}"
                            self.__log.log_message(error_message)
                        state = device.state.upper()

                        # Successfully open the door
                        if previous_state == "OPENING" and state == "OPEN":
                            self.__log.log_message(f"Actual time to Open the door:{time.monotonic()- self.opening_timer_start}")
                            self.__throttle_delay = 60

                        # Successfully close the door
                        if previous_state == "CLOSING" and state == "CLOSED":
                            self.__log.log_message(f"Actual time to Close the door:{time.monotonic()- self.closing_timer_start}")
                            self.__throttle_delay = 60

                        # The garage door position has changed
                        if state != self.garage_state[device.name]["state"] and state in ["OPEN", "CLOSED"]:
                            last_update = datetime.datetime.now()
                            with self.lock_access:
                                self.garage_state[device.name] = {
                                    "state": state,
                                    "last_update": last_update
                                }
                                self.__log.log_message(f"New Door State: {state} {last_update}")
                                #(f"Thread:New Door State: {state} {last_update}")

                        # Did not succeed to open the door
                        if state == "OPENING" and time.monotonic() - self.opening_timer_start >= self.opening_max_delay:
                            self.__log.log_message(f"Seems door did not open after {self.opening_max_delay}sec, will reset myQ")
                            self.loop_myq = False
                            reset_myq = True

                        # Did not succeed to close the door
                        if state == "CLOSING" and time.monotonic() - self.closing_timer_start >= self.closing_max_delay:
                            self.__log.log_message(f"Seems door did not close after {self.closing_max_delay}sec, will reset myQ")
                            self.loop_myq = False
                            reset_myq = True
                    else:
                        time.sleep(.1)

                    # Check if we need to Open/Close the door
                    with self.lock_access:
                        will_open = self.need_to_open_the_door
                        will_close = self.need_to_close_the_door

                    # Close the garage Door
                    if will_close:
                        self.__log.log_message("Will Close the door")
                        try:
                            await device.close(wait_for_state=False)
                        except Exception as err:
                            function = inspect.stack()[0].function
                            error_message = f"{function=}, {Exception=}, {err=}"
                            self.__log.log_message(error_message)
                        with self.lock_access:
                            self.need_to_close_the_door = False

                    # Open the garage Door
                    if will_open:
                        self.__log.log_message("Will Open the door")
                        try:
                            await device.open(wait_for_state=False)
                        except Exception as err:
                            function = inspect.stack()[0].function
                            error_message = f"{function=}, {Exception=}, {err=}"
                            self.__log.log_message(error_message)
                        with self.lock_access:
                            self.need_to_open_the_door = False

                    # if time.monotonic() >= self.main_alive + 120:
                    #     self.__log.log_message("Main thread seems to be dead")
                    #     self.loop_myq = False
                if reset_myq is True:
                    self.loop_myq = True
                    self.__throttle_delay = 60
                print("Ending thread myqSH")
            else:
                self.garage_state['Porte de Garage'] = {
                    "state": "CLOSED",
                    "last_update": datetime.datetime.now()
                }
                while self.loop_myq:
                    if time.monotonic() >= self.__next_query:
                        self.__next_query = time.monotonic() + self.__throttle_delay
                    else:
                        time.sleep(1)
                print("Ending thread myqSH")

    def close(self):
        if not self.module_enable:
            return
        with self.lock_access:
            self.need_to_close_the_door = True
            self.closing_timer_start = time.monotonic()
            self.__throttle_delay = 1

    def open(self):
        if not self.module_enable:
            return
        with self.lock_access:
            self.need_to_open_the_door = True
            self.opening_timer_start = time.monotonic()
            self.__throttle_delay = 1

    def get_state(self):
        with self.lock_access:
            state = self.garage_state
            self.main_alive = time.monotonic()
        return state

    def wait_for_initialisation(self):
        i = 0
        while self.get_state() == {} or i >= 10:
            time.sleep(1)
            i += 1
        return

def main():
    door_id = 'CG084682B7C9'
    myq = MyQIntegration('stephanetrudelle@gmail.com', door_id, module_enable=False)
    myq.start()
    myq.wait_for_initialisation()

    # i = 0
    # garage_devices = myq.get_state()
    # while garage_devices == {}:
    #     print(f"{i}:Wait for myQ initialisation")
    #     time.sleep(1)
    #     garage_devices = myq.get_state()
    #     i += 1

    garage_devices = myq.get_state()
    state = garage_devices['Porte de Garage']['state']
    last_update = garage_devices['Porte de Garage']['last_update']
    print(f"Initial Door State: {state} {last_update}")

    print("Will monitor things 10 seconds")
    for i in range(0, 10):
        time.sleep(1)
        garage_devices = myq.get_state()
        state = garage_devices['Porte de Garage']['state']
        last_update = garage_devices['Porte de Garage']['last_update']
        print(f"{i}:{state} {last_update}")

    print("Request to Open Door")
    myq.open()

    print("Will monitor things 60 seconds")
    for i in range(0, 60):
        garage_devices = myq.get_state()
        state = garage_devices['Porte de Garage']['state']
        last_update = garage_devices['Porte de Garage']['last_update']
        print(f"{i}:{state} {last_update}")
        time.sleep(1)

    print("Request to Close Door")
    myq.close()

    print("Will monitor things 60 seconds")
    for i in range(0, 60):
        garage_devices = myq.get_state()
        state = garage_devices['Porte de Garage']['state']
        last_update = garage_devices['Porte de Garage']['last_update']
        print(f"{i}:{state} {last_update}")
        time.sleep(1)

    myq.loop_myq = False

    print("Done")


def monitor():
    door_id = 'CG084682B7C9'
    myq = MyQIntegration('stephanetrudelle@gmail.com', door_id, module_enable=False)
    myq.start()
    myq.wait_for_initialisation()

    # i = 0
    # garage_devices = myq.get_state()
    # while garage_devices == {}:
    #     print(f"{i}:Wait for myQ initialisation")
    #     time.sleep(1)
    #     garage_devices = myq.get_state()
    #     i += 1

    garage_devices = myq.get_state()
    state = garage_devices['Porte de Garage']['state']
    last_update = garage_devices['Porte de Garage']['last_update']
    print(f"Initial Door State: {state} {last_update}")
    previous_state = state

    for i in range(0, 100):
        state = garage_devices['Porte de Garage']['state']
        last_update = garage_devices['Porte de Garage']['last_update']
        if state != previous_state:
            print(f"Porte de Garage:{state} {last_update}")
        previous_state = state
        time.sleep(1)


if __name__ == '__main__':
    main()
