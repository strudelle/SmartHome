import datetime
import time
import requests
from libraries.util import LoggerSH, minute_to_hhmm


class WeatherIntegration:

    def __init__(self, latitude, longitude):
        print(f"Init: {self.__class__.__name__}")
        self.__log_err = LoggerSH(to_console=False, log_file_name=f"{self.__class__.__name__}_err.txt")
        self.__log_weather = LoggerSH(to_console=False, log_file_name=f"{self.__class__.__name__}_weather.txt")
        self.__latitude = latitude
        self.__longitude = longitude
        self.__throttle_delay = 30 * 60  # seconds
        self.__next_query = time.monotonic()
        self.__weather_dict = {}
        self.__base_url = "https://api.open-meteo.com/v1/forecast"

    def read_weather_condition(self):
        if time.monotonic() >= self.__next_query:
            self.__next_query = time.monotonic() + self.__throttle_delay
            try:
                # Open-Meteo API parameters
                params = {
                    "latitude": self.__latitude,
                    "longitude": self.__longitude,
                    "current_weather": "true",
                    "hourly": "cloudcover,precipitation,precipitation_type",
                    "timezone": "auto"
                }
                
                # Make API request to Open-Meteo
                response = requests.get(self.__base_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                # Extract current weather data
                current_weather = data.get("current_weather", {})
                hourly_data = data.get("hourly", {})
                
                # Map Open-Meteo data to match existing structure
                self.__weather_dict['temperature'] = current_weather.get('temperature', 0)
                self.__weather_dict['weather_text'] = self._get_weather_description(current_weather.get('weathercode', 0))
                self.__weather_dict['local_observation_datetime'] = current_weather.get('time', '')
                self.__weather_dict['cloud_cover'] = self._get_current_cloud_cover(hourly_data)
                self.__weather_dict['has_precipitation'] = self._check_precipitation(hourly_data)
                self.__weather_dict['precipitation_type'] = self._get_precipitation_type(hourly_data)
                self.__weather_dict['remaining'] = "N/A"  # Open-Meteo doesn't have request limits
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
                
            except Exception as err:
                error_message = f"{Exception=}, {err=}"
                self.__log_err.log_message(error_message)
        return self.__weather_dict

    def _get_weather_description(self, weather_code):
        """Convert Open-Meteo weather code to descriptive text"""
        weather_descriptions = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            56: "Light freezing drizzle",
            57: "Dense freezing drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            66: "Light freezing rain",
            67: "Heavy freezing rain",
            71: "Slight snow fall",
            73: "Moderate snow fall",
            75: "Heavy snow fall",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail"
        }
        return weather_descriptions.get(weather_code, "Unknown")

    def _get_current_cloud_cover(self, hourly_data):
        """Get current cloud cover from hourly data"""
        cloudcover = hourly_data.get('cloudcover', [])
        if cloudcover:
            return cloudcover[0]  # First hour is current
        return 0

    def _check_precipitation(self, hourly_data):
        """Check if there's precipitation in the current hour"""
        precipitation = hourly_data.get('precipitation', [])
        if precipitation:
            return precipitation[0] > 0  # True if precipitation > 0
        return False

    def _get_precipitation_type(self, hourly_data):
        """Get precipitation type from hourly data"""
        precipitation_type = hourly_data.get('precipitation_type', [])
        if precipitation_type:
            type_code = precipitation_type[0]
            type_mapping = {
                0: "None",
                1: "Rain",
                2: "Snow",
                3: "Freezing rain",
                4: "Ice pellets"
            }
            return type_mapping.get(type_code, "Unknown")
        return "None"

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
