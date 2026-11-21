import datetime
import time
from dateutil.parser import parse
from decora_wifi import DecoraWiFiSession
from decora_wifi.models.residential_account import ResidentialAccount
from libraries.util import LoggerSH
import inspect
import keyring


class LevitonIntegration:
    def __init__(self, username, log, password=None):
        print(f"Init: {self.__class__.__name__}")
        self.__log = LoggerSH(to_console=False, log_file_name=f"{self.__class__.__name__}_err.txt")
        self.permission = None
        self.residence = None
        self._username = username
        self._password = password if password else keyring.get_password("leviton", username)
        self.connected = False
        self.session = DecoraWiFiSession()
        self.reconnect_count = 0
        self.disconnect_time = None
        self.__next_reconnect = time.monotonic()
        self.connection_failed = False
        self.switch_object = {}
        self.__main_log = log

    def connect(self):
        try:
            self.session.login(self._username, self._password)
            self.permission = self.session.user.get_residential_permissions()[0]

            residential_count_id = self.permission.residentialAccountId
            acct = ResidentialAccount(self.session, residential_count_id)
            self.residence = acct.get_residences()[0]
            self.connected = True
        # except ValueError:
        except Exception as err:
            self.connected = False
            self.connection_failed = True
            self.disconnect_time = datetime.datetime.now()
            function = inspect.stack()[0].function
            error_message = f"{function=}, {Exception=}, {err=}"
            self.__log.log_message(error_message)

        return self.session

    def reconnect(self):
        if time.monotonic() >= self.__next_reconnect:
            self.connect()
            if self.connected:
                self.disconnect_time = None
                self.reconnect_count = 0
            else:
                self.reconnect_count += 1
                self.connection_failed = True
                # For the first minute, try to reconnect every 5 seconds
                if self.reconnect_count < 12:
                    self.__next_reconnect = time.monotonic() + 5
                else:
                    # After 1 minute, try to reconnect every minute
                    self.__next_reconnect = time.monotonic() + 60

    def get_permission(self):
        return self.permission

    def get_residence(self):
        return self.residence

    def get_all_switches(self):
        all_switches_dict = {}
        if self.connected:
            try:
                all_switches = self.residence.get_iot_switches()
                if len(self.switch_object) == 0:
                    for switch in all_switches:
                        self.switch_object[switch.data['name']] = switch
                for switch in all_switches:
                    all_switches_dict[switch.data['name']] = {
                        "api": "leviton",
                        "type": "switch",
                        "state": switch.data['power'].upper(),
                        "dimmer": switch.data['canSetLevel'],
                        "level": switch.data['brightness'],
                        "max_level": switch.data['maxLevel'],
                        "min_level": switch.data['minLevel'],
                        "last_update": parse(str(parse(switch.data['lastUpdated']).astimezone())[:-6]),
                        "online": switch.data['connected'],
                        "signal_strength": switch.data['rssi'],
                        "connected": datetime.datetime.fromtimestamp(int(switch.data['connectedTimestamp'])/1000),
                        "virtual": False
                    }
                    # if switch.data['name'] == 'Lumière foyer':
                    #     for key in switch.data.keys():
                    #         print(f"{key}\t{switch.data[key]}")

            # except ValueError:
            except Exception as err:
                self.connected = False
                self.connection_failed = True
                self.disconnect_time = datetime.datetime.now()
                function = inspect.stack()[0].function
                error_message = f"{function=}, {Exception=}, {err=}"
                self.__log.log_message(error_message)
        return all_switches_dict

    def set_switch(self, switches_name, switch_value):
        if self.connected:
            if not isinstance(switches_name, list):
                switches_name = [switches_name]
            for switch_name in switches_name:
                try:
                    message = f"SET:'{switch_name}'\t{switch_value}"
                    self.__main_log.log_message(message)
                    self.switch_object[switch_name].update_attributes({'power': switch_value.upper()})
                    # except ValueError:
                except Exception as err:
                    self.connected = False
                    self.connection_failed = True
                    self.disconnect_time = datetime.datetime.now()
                    function = inspect.stack()[0].function
                    error_message = f"{function=}, {Exception=}, {err=}"
                    self.__log.log_message(error_message)
        return

    def set_level(self, switch_name, switch_value):
        if self.connected:
            try:
                message = f"SET:'{switch_name}'\t{switch_value}"
                self.__main_log.log_message(message)
                self.switch_object[switch_name].update_attributes({'brightness': switch_value, 'power': "ON"})
                # except ValueError:
            except Exception as err:
                self.connected = False
                self.connection_failed = True
                self.disconnect_time = datetime.datetime.now()
                function = inspect.stack()[0].function
                error_message = f"{function=}, {Exception=}, {err=}"
                self.__log.log_message(error_message)
        return
