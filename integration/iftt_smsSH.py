import requests
from libraries.util import LoggerSH
import keyring


class Iftt:
    def __init__(self, key=None):
        print(f"Init: {self.__class__.__name__}")
        self.__log_err = LoggerSH(to_console=False, log_file_name=f"{self.__class__.__name__}_err.txt")
        self.key = key if key else keyring.get_password("iftt", "key")
        self.headers = {'Content-Type': 'application/json'}

    def send_sms(self, sms_text):
        event = "send_sms"
        url = f'https://maker.ifttt.com/trigger/{event}/with/key/{self.key}'
        data = '{"value1": ' + f'"{sms_text}"' + '}'
        try:
            response = requests.post(url, headers=self.headers, data=data)
            if response.status_code != 200:
                error_message = f"Error: {event} {response.status_code} {response.reason}"
                self.__log_err.log_message(error_message)
        except Exception as err:
            error_message = f"{Exception=}, {err=}"
            self.__log_err.log_message(error_message)


def main():
    iftt = Iftt()
    iftt.send_sms("From python class")


if __name__ == '__main__':
    main()
