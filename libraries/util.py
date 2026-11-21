import time
import datetime
from dateutil.parser import parse
import os
from suntime import Sun
import sched
import signal
from threading import Lock

class LoggerSH:
    def __init__(self, heart_beat_delay=0, to_console=True, log_file_name=""):
        self.lock_access = Lock()
        log_path = "logs"
        self.start_time = time.monotonic()
        self.delay = heart_beat_delay
        self.time_to_log = self.start_time + self.delay
        self.to_console = to_console
        self.log_file_name = log_file_name
        self.to_file = False
        if len(self.log_file_name):
            os.makedirs(log_path, exist_ok=True)
            full_path = os.path.join(log_path, log_file_name)
            self.to_file = True
            self.f = open(full_path, 'a')
        log_string = f"Start Logging at :{str(datetime.datetime.now())[:-4]}"
        self._do_log_change(log_string)

    def log_alive(self):
        now = time.monotonic()
        if now >= self.time_to_log:
            self.time_to_log = self.time_to_log + self.delay
            formatted_time = self.format_time(now - self.start_time)
            log_string = f"Alive: {str(datetime.datetime.now())[:-4]}\tRun Time: {formatted_time}"
            self._do_log_change(log_string)

    def log_changes(self, switch_name, switch_value):
        log_string = f"{str(datetime.datetime.now())[:-4]}\t'{switch_name}'\t{switch_value}"
        # log_string = f"'{switch_name}'"
        self._do_log_change(log_string)

    def log_message(self, message):
        log_string = f"{str(datetime.datetime.now())[:-4]}\t{message}"
        self._do_log_change(log_string)

    def _do_log_change(self, string_to_log):
        with self.lock_access:
            if self.to_file:
                self.f.write(f"{string_to_log}\n")
                self.f.flush()
            if self.to_console:
                print(f"{string_to_log}")

    @staticmethod
    def format_time(seconds):
        hours = seconds // (60 * 60)
        seconds %= (60 * 60)
        minutes = seconds // 60
        seconds %= 60
        return "%02i:%02i:%02i" % (hours, minutes, seconds)


class EventsScheduler:
    def __init__(self, log):
        self.log = log
        self.scheduler = sched.scheduler(time.monotonic, time.sleep)

    def run(self, blocking):
        return self.scheduler.run(blocking=blocking)

    def enter(self, delay, priority, action, argument):
        event_time = datetime.datetime.now() + datetime.timedelta(seconds=delay)
        message = f"EventsScheduler: Will change '{argument[0]}' to {argument[1]} at {str(event_time)[:-4]}"
        self.log.log_message(message)
        return self.scheduler.enter(delay, priority, action, argument=argument)

    def cancel(self, switch_name):
        for event in self.scheduler.queue:
            if event.argument[0] == switch_name:
                message = f"EventsScheduler: Canceling event to change '{event.argument[0]}' to {event.argument[1]}"
                self.log.log_message(message)
                return self.scheduler.cancel(event)


class SignalHandler:
    shutdown_requested = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.request_shutdown)
        signal.signal(signal.SIGTERM, self.request_shutdown)

    def request_shutdown(self, *args):
        print('Request to shutdown received, stopping')
        self.shutdown_requested = True

    def can_run(self):
        return not self.shutdown_requested


class SunSH:
    def __init__(self, lat, lon):
        self.sun = Sun(lat, lon)

    def sunrise(self):
        """
        return today's sunrise time on format "05:23:45"
        :return:
        """
        today = datetime.datetime.today().date()
        return self.sun.get_local_sunrise_time(today).strftime("%H:%M:%S")

    def sunset(self):
        """
        return today's sunset time on format "21:23:45"
        :return:
        """
        today = datetime.datetime.today().date()
        return self.sun.get_local_sunset_time(today).strftime("%H:%M:%S")


class TimeTriggerSH:
    def __init__(self):
        self.__time_reach = {}

    def time_is(self, at_time):
        """
        Will return True if we reach the specified time at_time
        :param at_time: "17:05:12" or "17:05"
        :return: True or False
        """
        # Compute the end_time as a string in the format "00:00:00" as being the at_time + 2 minutes
        at_time = format_time_hhmmss(at_time)
        if at_time not in self.__time_reach:
            self.__time_reach[at_time] = False
        time_end = (parse(at_time)+datetime.timedelta(minutes=2)).strftime("%H:%M:%S")
        if is_between_time(at_time, time_end):
            if self.__time_reach[at_time] is False:
                self.__time_reach[at_time] = True
                return True
            else:
                return False
        else:
            self.__time_reach[at_time] = False
            return False


def format_time_hhmmss(time_str: str) -> str:
    """
    Convert a time string to make sure it meets the format "hh:mm:ss".  Thus
    "hh" become "hh:00:00"
    "hh:mm" become "hh:mm:00"
    "hh:mm:ss" stay un-change"
    :param time_str:
    :return: string in format "hh:mm:ss"
    count the number of : in the string and will make the following assumptions
    """
    str_len = len(time_str)
    number_of_column = str_len - len(time_str.replace(":", ""))
    if str_len == 2 and number_of_column == 0:
        time_str = time_str + ":00:00"
    elif str_len == 5 and number_of_column == 1:
        time_str = time_str + ":00"
    elif str_len != 8 or number_of_column != 2:
        raise ValueError
    return time_str


def minute_to_hhmm(number_of_minutes: int) -> str:
    """
    Convert int time in str format hh:mm
    :param number_of_minutes:
    :return:
    """
    return time.strftime('%H:%M', time.gmtime(number_of_minutes * 60))


def get_time_now():
    return datetime.datetime.today().strftime("%H:%M:%S")


def is_between_time(time_start: str, time_end: str, time_now: str = "") -> bool:
    """
    If time_now is not specified, will check that current time is between time_start and time_end
    If time_now is specified it will check if the specified time is between time_start and time_end
    The function takes into account days change.  Example
    is_between_time("11:00", "13:00") current time is 12:00, will return True
    is_between_time("11:00", "13:00") current time is 2:00 (am), will return False
    is_between_time("23:00", "02:00") current ime is 1:00 (am), will return True

    :param time_start: Format  "11", 13:05", or "17:05:12"
    :param time_end: Format "11", "13:05", or "17:05:12"
    :param time_now: Format "11", "13:05", or "17:05:12", current time by default
    :return: True or False
    """
    if len(time_now) == 0:
        time_now = get_time_now()
    else:
        time_now = format_time_hhmmss(time_now)
    time_start = format_time_hhmmss(time_start)
    time_end = format_time_hhmmss(time_end)

    if time_end < time_start:
        return time_now >= time_start or time_now < time_end
    return time_start <= time_now < time_end


def calculate_time(delta_time_in, modfifier_type_in, base_time_in):
    """
    ("10:00", "after", get_time_now())
    """
    if modfifier_type_in.lower() == "before":
        modifier_type = -1
    else:
        modifier_type = 1
    base_time = parse(format_time_hhmmss(base_time_in))
    delta_time = parse(format_time_hhmmss(delta_time_in)).time()
    delta_hour = delta_time.hour * modifier_type
    delta_minute = delta_time.minute * modifier_type
    delta_second = delta_time.second * modifier_type
    final_time = base_time + datetime.timedelta(hours=delta_hour, minutes=delta_minute, seconds=delta_second)
    return final_time.strftime("%H:%M:%S")


def merge_dict(*dict_to_merge):
    merged_dict = {}
    for one_dict in dict_to_merge:
        merged_dict.update(one_dict)
    return merged_dict
