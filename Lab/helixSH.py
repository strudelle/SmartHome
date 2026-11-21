from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import os
import logging

import time
from libraries.util import LoggerSH

# Suppress webdriver-manager verbose logging
os.environ['WDM_LOG'] = '0'
os.environ['WDM_PRINT_FIRST_LINE'] = 'False'
logging.getLogger('WDM').setLevel(logging.WARNING)

# https://chromedriver.chromium.org/downloads
# or better: https://googlechromelabs.github.io/chrome-for-testing/
#  download chromedriver	win64
# copy to C:\Windows


log = LoggerSH(to_console=True, log_file_name=f"devices_status.log")

look_up = {"9a:41:9d:95:3c:9b": "LT",
           "s20-fe-de-stephane": "ST",
           "s20-fe-de-mathieu": "MT",
           "Pixel-8": "CD",
           "Nicolas-s-A36": "NL",
           }

# Track presence status for devices in look_up
# Format: {device_name_lower: {"status": "present"/"absent", "disconnect_time": timestamp or None}}
device_presence = {}
PRESENCE_TIMEOUT = 15 * 60  # 15 minutes in seconds


def wait_for_page_to_load(driver, time_out):
    end_time = time.time() + time_out
    while time.time() < end_time:
        x = driver.execute_script("return document.readyState")
        if x == "complete":
            return True
        else:
            time.sleep(.1)
    return False


def print_devices(device_list, message):
    all = False
    for device in device_list:
        who = look_up.get(device.lower(), "")
        if len(who):
            who = f":({who})"
            log.log_message(f"{device}{who}\t{message}")
        elif all:
            log.log_message(f"{device}\t{message}")


def update_presence_status(connected_devices_set):
    """Update presence status for tracked devices and log changes."""
    current_time = time.time()
    connected_lower = {dev.lower() for dev in connected_devices_set}
    
    # Check each device in look_up
    for device_key, device_code in look_up.items():
        device_lower = device_key.lower()
        is_connected = device_lower in connected_lower
        
        # Initialize device in tracking if not present
        if device_key not in device_presence:
            if is_connected:
                device_presence[device_key] = {"status": "present", "disconnect_time": None}
                log.log_message(f"{device_code} ({device_key}): PRESENCE CHANGED -> PRESENT")
            else:
                device_presence[device_key] = {"status": "absent", "disconnect_time": current_time}
                log.log_message(f"{device_code} ({device_key}): PRESENCE CHANGED -> ABSENT")
            continue
        
        current_status = device_presence[device_key]["status"]
        disconnect_time = device_presence[device_key]["disconnect_time"]
        
        if is_connected:
            # Device is currently connected
            if current_status == "absent":
                # Device was absent and now reconnected -> mark as present
                device_presence[device_key] = {"status": "present", "disconnect_time": None}
                log.log_message(f"{device_code} ({device_key}): PRESENCE CHANGED -> PRESENT")
            elif current_status == "present":
                # Device was present, clear disconnect time if it exists
                device_presence[device_key]["disconnect_time"] = None
        else:
            # Device is not currently connected
            if current_status == "present":
                # Device was present, check if we need to record disconnect time or mark as absent
                if disconnect_time is None:
                    # Just disconnected - record the disconnect time
                    device_presence[device_key]["disconnect_time"] = current_time
                else:
                    # Already have a disconnect time, check if it's been > 15 minutes
                    time_disconnected = current_time - disconnect_time
                    if time_disconnected >= PRESENCE_TIMEOUT:
                        # Been disconnected for more than 15 minutes -> mark as absent
                        device_presence[device_key]["status"] = "absent"
                        log.log_message(f"{device_code} ({device_key}): PRESENCE CHANGED -> ABSENT (disconnected for {int(time_disconnected/60)} minutes)")
            # If status is already "absent", no action needed


def start_browser():
    options = Options()
    options.add_argument("--headless=new")
    # Automatically downloads and manages the correct ChromeDriver version
    try:
        driver_path_returned = ChromeDriverManager().install()
        log.log_message(f"ChromeDriverManager returned: {driver_path_returned}")
        driver_path = driver_path_returned.replace('/THIRD_PARTY_NOTICES.chromedriver', '\\chromedriver.exe')
        
        log.log_message(f"Using ChromeDriver path: {driver_path}")
        service = Service(driver_path)
        browser = webdriver.Chrome(service=service, options=options)
    except Exception as err:
        log.log_message(f"Error setting up ChromeDriver: {type(err).__name__}: {err}")
        raise

    # load page
    url = 'http://10.0.0.1/'
    try:
        browser.get(url)
        wait_for_page_to_load(browser, 10)
    except Exception as err:
        log.log_message(f"Error loading page: {type(err).__name__}: {err}")
        browser.quit()
        raise
    
    return browser


def login(browser):
    browser.find_element(by=By.ID, value="username").send_keys("admin")
    browser.find_element(by=By.ID, value="password").send_keys("shawinigan")
    browser.find_element(by=By.CLASS_NAME, value="btn").click()
    wait_for_page_to_load(browser, 10)


while True:
    a = ""
    no_error = True
    web_browser = None
    while not web_browser:
        try:
            web_browser = start_browser()
        except Exception as err:
            error_message = f"Exception type: {type(err).__name__}, Error: {err}"
            log.log_message(f"Problem starting browser: {error_message}")
            log.log_message(f"Will try again in 5 minutes")
            time.sleep(300)

    login(web_browser)
    devices = web_browser.find_element(by=By.ID, value="internet-usage")
    devices_text = devices.text.split('\n')
    connected_devices = set(devices_text[1:-1])
    print_devices(connected_devices, "Connected")
    # Initialize presence status for initially connected devices
    update_presence_status(connected_devices)

    while no_error:
        time.sleep(10)
        try:
            web_browser.refresh()
            a = wait_for_page_to_load(web_browser, 10)
            devices = web_browser.find_element(by=By.ID, value="internet-usage")
        except Exception as err:
            error_message = f"{Exception=}, {err=}"
            log.log_message(f"{error_message=} {a=} {devices=}")
            log.log_message(f"We will restart")
            web_browser.quit()
            no_error = False
        else:
            devices_refresh = devices.text.split('\n')
            connected_devices = set(devices_refresh[1:-1])
            
            devices_lost = set(devices_text) - connected_devices
            if devices_lost:
                print_devices(devices_lost, "Disconnected")
            devices_new = connected_devices - set(devices_text)
            if devices_new:
                print_devices(devices_new, "Connected")
            
            # Update presence status for tracked devices
            update_presence_status(connected_devices)
            
            devices_text = devices_refresh
