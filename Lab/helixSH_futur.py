from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

import time
from libraries.util import LoggerSH

# https://chromedriver.chromium.org/downloads
# or better: https://googlechromelabs.github.io/chrome-for-testing/
#  download chromedriver	win64
# copy to C:\Windows


look_up = {"9a:41:9d:95:3c:9b": "LT",
           "s20-fe-de-stephane": "ST",
           "s20-fe-de-mathieu": "MT",
           "galaxy-s10": "CD",
           "b2:a4:e9:2d:b5:57": "NL",
           "Air-de-Nicolas": "NL",
           "26:f0:b6:d7:f7:de": "AM",
           "1a:f8:ff:37:1c:84": "AS",
           }


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
    for device in device_list:
        who = look_up.get(device.lower(), "")
        if len(who):
            who = f":({who})"
        log.log_message(f"{device}{who}\t{message}")


def start_browser():
    options = Options()
    options.add_argument("--headless=new")
    browser = webdriver.Chrome(options=options)

    # load page
    url = 'http://10.0.0.1/'
    browser.get(url)
    wait_for_page_to_load(browser, 10)
    return browser


def login(browser):
    browser.find_element(by=By.ID, value="username").send_keys("admin")
    browser.find_element(by=By.ID, value="password").send_keys("shawinigan")
    browser.find_element(by=By.CLASS_NAME, value="btn").click()
    wait_for_page_to_load(browser, 10)


log = LoggerSH(to_console=True, log_file_name=f"devices_status.log")
while True:
    a = ""
    no_error = True
    web_browser = None
    while not web_browser:
        try:
            web_browser = start_browser()
        except:
            log.log_message(f"Problem starting browser, will try again in 5 minutes")
            time.sleep(300)

    login(web_browser)
    devices = web_browser.find_element(by=By.ID, value="internet-usage")
    devices_text = devices.text.split('\n')
    print_devices(devices_text[1:-1], "Connected")

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
            devices_lost = set(devices_text) - set(devices_refresh)
            if devices_lost:
                print_devices(devices_lost, "Disconnected")
            devices_new = set(devices_refresh) - set(devices_text)
            if devices_new:
                print_devices(devices_new, "Connected")
            devices_text = devices_refresh
