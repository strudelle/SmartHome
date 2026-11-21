import time
import datetime
from libraries.util import LoggerSH
import inspect
from PyL360 import L360Client
import keyring

# https://pypi.org/project/PyL360/
# https://github.com/arkangel-dev/PyL360

"""
There is two bug, that need to be fix in the code version 0.1.10 if you import again
1-C:\\Users\\steph\\AppData\\Roaming\\Python\\Python310\\site-packages\\PyL360\\__init__.py"
    def _printTypeError(exception: WrongTypeError, payload: str):
    Should be replaced with:
    def _printTypeError(self, exception: WrongTypeError, payload: str):

2-C:\\Users\\steph\\AppData\\Roaming\\Python\\Python310\\site-packages\\PyL360\\dto_models.py
@dataclass
Class Location:
    address1: str
    address2: str
    Should be replaced with:
    address1: Optional[str]
    address2: Optional[str]
"""


class Life360Integration:
    def __init__(self, username, circle_name, domicile_name, password=None, module_enable=True):
        self.module_enable = module_enable
        print(f'Init: {self.__class__.__name__}, Module:{"Enable" if module_enable else "Disabled"}')
        self.__log = LoggerSH(to_console=False, log_file_name=f"{self.__class__.__name__}_err.txt", heart_beat_delay=60)
        self.username = username
        self.circle_name = circle_name
        self.circleID = ''
        self.domicile_name = domicile_name
        self.__throttle_delay = 10
        self.__next_query = time.monotonic()
        if self.module_enable:
            self.life360 = L360Client(username, password if password else keyring.get_password("live360", username))
            self.life360.Authenticate()
            self._set_circle_id(self.circle_name)
            self.presence_state = {}
        else:
            self.presence_state = {'Léanne Presence': {
                "api": "life360",
                "type": "presence",
                "state": "NOT PRESENT"
            }}

    def _set_circle_id(self, name):
        circles = self.life360.GetCircles().circles
        for circle in circles:
            if circle.name == name:
                # print(f"Circle:{circle.name} - {circle.id}")
                self.circleID = circle.id

    def get_all_presence_state(self):
        self.__log.log_alive()
        if self.module_enable and time.monotonic() >= self.__next_query:
            self.__next_query = time.monotonic() + self.__throttle_delay
            # start_time = time.monotonic()

            try:
                # print(time.monotonic())
                circle = self.life360.GetCircle(self.circleID)
                for member in circle.members:
                    # presence_name = self.__presence_lookup[user_position['userId']]
                    # position_raw = user_position['name']
                    if member.location.name == self.domicile_name:
                        position = 'PRESENT'
                    else:
                        position = 'NOT PRESENT'
                    presence_key = f"{member.firstName} Presence"
                    self.presence_state[presence_key] = {
                        "api": "life360",
                        "type": "presence",
                        "state": position.upper(),
                        "name": member.location.name,
                        "adresse1": member.location.address1,
                        "adresse2": member.location.address1,
                        "latitude": member.location.latitude,
                        "longitude": member.location.longitude
                    }
                    # if member.firstName == "Léanne":
                    #     print(f"{member.firstName}: {self.presence_state[member.firstName]}")
            except Exception as err:
                function = inspect.stack()[0].function
                error_message = f"{function=}, {Exception=}, {err=}"
                self.__log.log_message(error_message)

            # print(f"{datetime.datetime.now()} Elapse: {time.monotonic()-start_time}")
        return self.presence_state

# NEW: NDRiMzNmOTAtZGJkNy00M2VhLWJhYWUtMTBjMDVlNWFlZWE5
def main():

    life360 = Life360Integration('stephanetrudelle@gmail.com', 'Famille Trudelle', 'Domicile')
    all_devices_previous = life360.get_all_presence_state().copy()

    for persone in all_devices_previous:
        print(f"{str(datetime.datetime.now())[:-4]}\t'{persone}'\t{all_devices_previous[persone]['state']}")
        # print(f"{str(datetime.datetime.now())[:-4]}\t'{persone}'\t{all_devices_previous[persone]['state']}"
        #       f"\t{all_devices_previous[persone]['name']}"
        #       f"\t{all_devices_previous[persone]['adresse1']}"
        #       f"\t{all_devices_previous[persone]['adresse2']}"
        #       f"\t{all_devices_previous[persone]['latitude']}"
        #       f"\t{all_devices_previous[persone]['longitude']}")

    while True:
        # start = time.monotonic()
        all_devices_updated = life360.get_all_presence_state()
        # print(time.monotonic()-start)
        for device_name in all_devices_updated.keys():
            device_value_updated = all_devices_updated[device_name]['state']
            device_value_previous = all_devices_previous[device_name]['state']
            if device_value_previous != device_value_updated:
                all_devices_previous[device_name]['state'] = device_value_updated
                print(f"{str(datetime.datetime.now())[:-4]}\t'{device_name}'\t{device_value_updated}")

    # while True:
    #     all_devices_updated = life360.get_all_presence_state()
    #     for persone in all_devices_updated.keys():
    #         if all_devices_updated[persone] != all_devices_previous[persone]:
    #             print(f"{str(datetime.datetime.now())[:-4]}\t'{persone}'\t{all_devices_updated[persone]['state']}"
    #                   f"\t{all_devices_updated[persone]['name']}"
    #                   f"\t{all_devices_updated[persone]['adresse1']}"
    #                   f"\t{all_devices_updated[persone]['adresse2']}"
    #                   f"\t{all_devices_updated[persone]['latitude']}"
    #                   f"\t{all_devices_updated[persone]['longitude']}")
    #             all_devices_previous[persone] = all_devices_updated[persone].copy()


if __name__ == '__main__':
    main()
