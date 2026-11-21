import requests
import time
import datetime
from libraries.util import LoggerSH
import inspect
import keyring


class Life360Integration:
    def __init__(self, username, circle_name, domicile_name, module_enable=True, password=None):
        self.module_enable = module_enable
        print(f'Init: {self.__class__.__name__}, Module:{"Enable" if module_enable else "Disabled"}')
        self.__log = LoggerSH(to_console=False, log_file_name=f"{self.__class__.__name__}_err.txt")
        self.username = username
        self.circle_name = circle_name
        self.domicile_name = domicile_name
        self.__throttle_delay = 10
        self.__next_query = time.monotonic()
        self.__presence_lookup = {
            'ceff30b3-e686-4de5-9a89-76c5e0aa1d0b': 'Stephane Presence',
            'dcc21763-a98a-4a9e-ac6a-729cf1aa78ac': 'Leanne Presence'}
        if self.module_enable:
            self.life360 = Life360_obsolete(username, password if password else keyring.get_password("live360", username))
            self.life360.get_circle()
            self.life360.set_circle(circle_name)
            self.presence_state = {}
        else:
            self.presence_state = {'Leanne Presence': {
                "api": "life360",
                "type": "presence",
                "state": "NOT PRESENT"
            }}

    def get_all_presence_state(self):
        if self.module_enable and time.monotonic() >= self.__next_query:
            self.__next_query = time.monotonic() + self.__throttle_delay
            try:
                # print(time.monotonic())
                history_data = self.life360.history()
                for user_position in history_data:
                    presence_name = self.__presence_lookup[user_position['userId']]
                    position_raw = user_position['name']
                    if position_raw == self.domicile_name:
                        position = 'PRESENT'
                    else:
                        position = 'NOT PRESENT'
                    self.presence_state[presence_name] = {
                        "api": "life360",
                        "type": "presence",
                        "state": position.upper()
                    }
            except Exception as err:
                function = inspect.stack()[0].function
                error_message = f"{function=}, {Exception=}, {err=}"
                self.__log.log_message(error_message)
        return self.presence_state


class Life360_obsolete:

    def __init__(self, username, password):
        self.circleID = ''
        self.circleData = {}
        self.base_url_v4 = 'https://api-cloudfront.life360.com/v4/'
        self.base_url = 'https://api-cloudfront.life360.com/v3/'
        self.access_token = self.__get_access_token(username, password)
        self.headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.access_token}',
        }

    def circles_details(self):
        return requests.get(f'{self.base_url}circles', headers=self.headers).json()

    def get_circle(self):
        circles = self.circles_details()['circles']
        for circle in circles:
            self.circleData[circle['name']] = circle['id']
        return self.circleData

    def set_circle(self, circle_name):
        self.circleID = self.circleData[circle_name]

    def history(self):
        return requests.get(f'{self.base_url}circles/{self.circleID}/members/history',
                            headers=self.headers).json()['locations']

    def __get_access_token(self, username, password):
        headers = {
            'Accept': 'application/json',
            "user-agent": 'com.life360.android.safetymapd/KOKO/23.50.0 android/13',
            'Authorization': 'Basic Y2F0aGFwYWNyQVBoZUtVc3RlOGV2ZXZldnVjSGFmZVRydVl1ZnJhYzpkOEM5ZVlVdkE2dUZ1YnJ1SmVnZXRyZVZ1dFJlQ1JVWQ==',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = f'username={username}&password={password}&grant_type=password'

        a = requests.post(f'{self.base_url}oauth2/token', headers=headers, data=data).json()[
            'access_token']
        return a


def main():

    life360 = Life360Integration('stephanetrudelle@gmail.com', 'Famille Trudelle', 'Domicile')
    all_devices = life360.get_all_presence_state()

    for device in all_devices:
        print(f"{str(datetime.datetime.now())[:-4]}\t'{device}'\t{all_devices[device]['state']}")

    while True:
        # start = time.monotonic()
        all_devices_updated = life360.get_all_presence_state()
        # print(time.monotonic()-start)
        for device_name in all_devices_updated.keys():
            device_value_updated = all_devices_updated[device_name]['state']
            device_value_previous = all_devices[device_name]['state']
            if device_value_previous != device_value_updated:
                all_devices[device_name]['state'] = device_value_updated
                print(f"{str(datetime.datetime.now())[:-4]}\t'{device_name}'\t{all_devices[device_name]['state']}")


if __name__ == '__main__':
    main()
