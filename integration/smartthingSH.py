#!/usr/bin/python
import datetime
import aiohttp
import asyncio
import pysmartthings
import time
import inspect
from libraries.util import LoggerSH
import keyring


class SmartThingsIntegration:
    def __init__(self, log, token=None):
        print(f"Init: {self.__class__.__name__}")
        self.__log = LoggerSH(to_console=False, log_file_name=f"{self.__class__.__name__}_err.txt")
        self.__switch_state = {}
        self.__presence_state = {}
        self.__token = token if token else keyring.get_password("smartthing", "token")
        self.__throttle_delay = 2  # seconds
        self.__next_query = time.monotonic()
        self.__main_log = log
        self.__devices_to_query = [
            "Lumière de Noel",
            "vsCoucher",
            "vsLeanneOut",
            "vsDejeuner",
            "vsDisableAutoLightOff",
            "vsSoirée télé",
            "vsSouper",
            "vsStPresentGH",
            "vsStPresentST",
            "vsTravail",
            "Globe 1",
            "Globe 2",
            "Globe 3",
            "Fenêtre",
            "S20 FE de Mathieu",
            "S20 FE de Stephane"
        ]

    @staticmethod
    async def __refresh_device_status(device):
        try:
            await device.status.refresh()
        except:
            pass
        return device

    async def refresh_all_devices_status(self):
        if time.monotonic() >= self.__next_query:
            self.__next_query = time.monotonic() + self.__throttle_delay
            try:
                async with aiohttp.ClientSession() as session:
                    api = pysmartthings.SmartThings(session, self.__token)
                    # Get the list of device and basic information, but no status
                    devices = await api.devices()
                    # for i, d in enumerate(devices):
                    #     if "presenceSensor" in d.capabilities:
                    #         print(f'{i}-{d.label}')

                    # Build the list of device to query
                    # cors = [self.__refresh_device_status(device) for device in devices]
                    cors = []
                    # i = 0
                    for device in devices:
                        if device.label in self.__devices_to_query:
                            cors.append(self.__refresh_device_status(device))
                        # if "switch" in device.capabilities and device.device_type_name == "Virtual Switch":
                        #     cors.append(self.__refresh_device_status(device))
                        # if "presenceSensor" in device.capabilities:  # and "S20 FE" in device.label:
                        #     cors.append(self.__refresh_device_status(device))
                        # if "Globe" in device.label:
                        #     cors.append(self.__refresh_device_status(device))
                        # print(f"{i}-{device.label}")
                        # i = i + 1

                    for cor in asyncio.as_completed(cors):
                        device = await cor
                        if "switch" in device.capabilities:
                            if device.label in self.__switch_state:
                                previous_state = self.__switch_state[device.label]["state"]
                                previous_update = self.__switch_state[device.label]["last_update"]
                            else:
                                previous_state = ""
                                previous_update = datetime.datetime.now()
                            if previous_state == device.status.values['switch'].upper():
                                record_state = previous_state
                                record_last_update = previous_update
                            else:
                                record_state = device.status.values['switch'].upper()
                                record_last_update = datetime.datetime.now()
                            self.__switch_state[device.label] = {
                                "api": "smartthings",
                                "type": "switch",
                                "state": record_state,
                                "dimmer": "",
                                "level": "",
                                "online": "",
                                "virtual": device.device_type_name == 'Virtual Switch',
                                "last_update": record_last_update,
                            }
                        if "presenceSensor" in device.capabilities:
                            if device.label in self.__presence_state:
                                previous_state = self.__presence_state[device.label]["state"]
                                previous_update = self.__presence_state[device.label]["last_update"]
                            else:
                                previous_state = ""
                                previous_update = datetime.datetime.now()
                            if previous_state == device.status.values['presence'].upper():
                                record_state = previous_state
                                record_last_update = previous_update
                            else:
                                record_state = device.status.values['presence'].upper()
                                record_last_update = previous_update
                            self.__presence_state[device.label] = {
                                "api": "smartthings",
                                "type": "presence",
                                "state": record_state,
                                "last_update": record_last_update,
                            }
            except Exception as err:
                function = inspect.stack()[0].function
                error_message = f"{function=}, {Exception=}, {err=}"
                self.__log.log_message(error_message)

    def get_switch_state(self, switch_name):
        return self.__switch_state.get(switch_name).get("state")

    def get_all_switch_state(self):
        return self.__switch_state

    def get_presence_state(self, device_name):
        return self.__presence_state.get(device_name).get("presence")

    def get_all_presence_state(self):
        return self.__presence_state

    def set_switch_state(self, switches_name, state):
        if not isinstance(switches_name, list):
            switches_name = [switches_name]
        try:
            if state.upper() == "ON":
                asyncio.run(self.__set_switch_on(switches_name))
            else:
                asyncio.run(self.__set_switch_off(switches_name))
        except Exception as err:
            function = inspect.stack()[0].function
            error_message = f"{function=}, {Exception=}, {err=}"
            self.__log.log_message(error_message)

    async def __set_switch_on(self, switches_name):
        async with aiohttp.ClientSession() as session:
            api = pysmartthings.SmartThings(session, self.__token)
            devices = await api.devices()
            for device in devices:
                if device.label in switches_name:
                    message = f"SET:'{device.label}'\tON"
                    self.__main_log.log_message(message)
                    await device.switch_on()

    async def __set_switch_off(self, switches_name):
        async with aiohttp.ClientSession() as session:
            api = pysmartthings.SmartThings(session, self.__token)
            devices = await api.devices()
            for device in devices:
                if device.label in switches_name:
                    message = f"SET:'{device.label}'\tOFF"
                    self.__main_log.log_message(message)
                    await device.switch_off()
