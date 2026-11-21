import datetime
import time
from aiohttp import ClientSession
from accuweather import AccuWeather
from libraries.util import LoggerSH, minute_to_hhmm

"""
Based on AccuWeather, the service is now paying
I replaced ith weatherSH.py

"""


class WeatherIntegration:

    def __init__(self, api_key, location):
        print(f"Init: {self.__class__.__name__}")
        self.__log_err = LoggerSH(to_console=False, log_file_name=f"{self.__class__.__name__}_err.txt")
        self.__log_weather = LoggerSH(to_console=False, log_file_name=f"{self.__class__.__name__}_weather.txt")
        self.__api_key = api_key
        self.__location_key = location
        self.__throttle_delay = 30 * 60  # seconds
        self.__next_query = time.monotonic()
        self.__weather_dict = {}

    async def read_weather_condition(self):
        if time.monotonic() >= self.__next_query:
            self.__next_query = time.monotonic() + self.__throttle_delay
            async with ClientSession() as websession:
                try:
                    accuweather = AccuWeather(self.__api_key, websession, location_key=self.__location_key)
                    current_conditions = await accuweather.async_get_current_conditions()
                except Exception as err:
                    error_message = f"{Exception=}, {err=}"
                    self.__log_err.log_message(error_message)
                else:
                    self.__weather_dict['weather_text'] = current_conditions['WeatherText']
                    self.__weather_dict['local_observation_datetime'] = current_conditions['LocalObservationDateTime']
                    self.__weather_dict['has_precipitation'] = current_conditions['HasPrecipitation']
                    self.__weather_dict['precipitation_type'] = current_conditions['PrecipitationType']
                    self.__weather_dict['temperature'] = current_conditions['Temperature']['Metric']['Value']
                    self.__weather_dict['cloud_cover'] = current_conditions['CloudCover']
                    self.__weather_dict['remaining'] = accuweather.requests_remaining
                    self.__weather_dict['last_update'] = datetime.datetime.now()
                    # time offset calculation
                    # if cloud coverage <= 30%  0 min offset
                    x1 = 30
                    y1 = 0
                    # if cloud coverage <  70%  30 min offset
                    x2 = 80
                    y2 = 30
                    m = (y2 - y1) / (x2 - x1)
                    b = (y1 - m * x1)
                    cloud_cover = self.__weather_dict['cloud_cover']
                    if cloud_cover <= x1:
                        offset = 0
                    elif cloud_cover <= x2:
                        offset = m * self.__weather_dict['cloud_cover'] + b
                    else:
                        offset = 120
                    # + 30, we want a minimum od 30 min for the offset
                    self.__weather_dict['time_offset'] = minute_to_hhmm(offset + 30)
                    log_string = f"{self.__weather_dict['temperature']}C\t" \
                                 f"{self.__weather_dict['weather_text']}\t" \
                                 f"{self.__weather_dict['cloud_cover']}\t" \
                                 f"{self.__weather_dict['has_precipitation']}\t" \
                                 f"{self.__weather_dict['precipitation_type']}\t" \
                                 f"{self.__weather_dict['local_observation_datetime']}\t" \
                                 f"{self.__weather_dict['remaining']}\t" \
                                 f"{self.__weather_dict['last_update']}"
                    self.__log_weather.log_message(log_string)
                    self.__weather_dict['log_string'] = log_string
        return self.__weather_dict

# def main():
#     if os.name == 'nt':  # nt = windows, posix = linux
#         asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
#
#     sun = SunSH(LATITUDE, LONGITUDE)
#     time_trigger = TimeTriggerSH()
#     sunrise = sun.sunrise()
#     sunset = sun.sunset()
#
#     weather = WeatherIntegration(WEATHER_API_KEY, WEATHER_LOCATION_KEY)
#     start = time.monotonic()
#     a = asyncio.run(weather.read_weather_condition())
#     print(time.monotonic() - start)
#     print(f"a={a}")
#
#     while True:
#         if time_trigger.time_is("00:00"):
#             sunrise = sun.sunrise()
#             sunset = sun.sunset()
#         if is_between_time(sunrise, sunset):
#             start = time.monotonic()
#             a = asyncio.run(weather.read_weather_condition())
#             print(time.monotonic()-start)
#             print(f"a={a}")
#             time.sleep(5)
#         else:
#             time.sleep(60)
#
#
# if __name__ == '__main__':
#     main()
