from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

import time
import datetime
from libraries.util import LoggerSH

# https://chromedriver.chromium.org/downloads
# or better: https://googlechromelabs.github.io/chrome-for-testing/
#  download chromedriver	win64
# copy to C:\Windows


look_up = { "9a:41:9d:95:3c:9b": "LT",
            "s20-fe-de-stephane": "ST",
            "s20-fe-de-mathieu": "MT",
            "galaxy-s10": "CD",
            "b2:a4:e9:2d:b5:57": "NL",
            "26:F0:B6:D7:F7:DE": "AM1",
            "1a:f8:ff:37:1c:84": "AM2",
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


log = LoggerSH(to_console=True, log_file_name=f"devices_status.log")

# options = Options()
# options.add_argument("--headless=new")
# web_browser = webdriver.Chrome(options=options)
# web_browser.set_window_position(-1928, -8)
# web_browser.maximize_window()

# options = Options()
# options.add_argument("--headless=new")
web_browser = webdriver.Chrome()
# web_browser.set_window_position(-1928, -8)
# web_browser.maximize_window()

# load page
url = 'http://10.0.0.1/'
web_browser.get(url)
wait_for_page_to_load(web_browser, 10)
web_browser.find_element(by=By.ID, value="username").send_keys("admin")
web_browser.find_element(by=By.ID, value="password").send_keys("shawinigan")
web_browser.find_element(by=By.CLASS_NAME, value="btn").click()
wait_for_page_to_load(web_browser, 10)
devices = web_browser.find_element(by=By.ID, value="internet-usage")
devices_text = devices.text.split('\n')
print_devices(devices_text[1:-1], "Connected")

while True:
    time.sleep(10)
    try:
        web_browser.refresh()
        a = wait_for_page_to_load(web_browser, 10)
        devices = web_browser.find_element(by=By.ID, value="internet-usage")
    except Exception as err:
        error_message = f"{Exception=}, {err=}"
        log.log_message(f"{error_message=} {a=} {devices=}")
        # Closed window: 2023-11-26 16:35:27.35	error_message="Exception=<class 'Exception'>, err=NoSuchWindowException('no such window: target window already closed\\nfrom unknown error: web view not found\\n  (Session info: chrome=119.0.6045.124)', None, ['\\tGetHandleVerifier [0x00007FF71A4382B2+55298]', '\\t(No symbol) [0x00007FF71A3A5E02]', '\\t(No symbol) [0x00007FF71A2605AB]', '\\t(No symbol) [0x00007FF71A240038]', '\\t(No symbol) [0x00007FF71A2C6BC7]', '\\t(No symbol) [0x00007FF71A2DA15F]', '\\t(No symbol) [0x00007FF71A2C1E83]', '\\t(No symbol) [0x00007FF71A29670A]', '\\t(No symbol) [0x00007FF71A297964]', '\\tGetHandleVerifier [0x00007FF71A7B0AAB+3694587]', '\\tGetHandleVerifier [0x00007FF71A80728E+4048862]', '\\tGetHandleVerifier [0x00007FF71A7FF173+4015811]', '\\tGetHandleVerifier [0x00007FF71A4D47D6+695590]', '\\t(No symbol) [0x00007FF71A3B0CE8]', '\\t(No symbol) [0x00007FF71A3ACF34]', '\\t(No symbol) [0x00007FF71A3AD062]', '\\t(No symbol) [0x00007FF71A39D3A3]', '\\tBaseThreadInitThunk [0x00007FFC8542257D+29]', '\\tRtlUserThreadStart [0x00007FFC8678AA58+40]', ''])" a=True b=<selenium.webdriver.remote.webelement.WebElement (session="1c0072b8cc33a43fc3b916e694e34c78", element="5E659235DC73AF697B11736D6372EAFC_element_125")>
        # Going to login page: 2023-11-26 16:39:46.24	error_message='Exception=<class \'Exception\'>, err=NoSuchElementException(\'no such element: Unable to locate element: {"method":"css selector","selector":"[id="internet-usage"]"}\\n  (Session info: chrome=119.0.6045.124)\', None, [\'\\tGetHandleVerifier [0x00007FF71A4382B2+55298]\', \'\\t(No symbol) [0x00007FF71A3A5E02]\', \'\\t(No symbol) [0x00007FF71A2605AB]\', \'\\t(No symbol) [0x00007FF71A2A175C]\', \'\\t(No symbol) [0x00007FF71A2A18DC]\', \'\\t(No symbol) [0x00007FF71A2DCBC7]\', \'\\t(No symbol) [0x00007FF71A2C20EF]\', \'\\t(No symbol) [0x00007FF71A2DAAA4]\', \'\\t(No symbol) [0x00007FF71A2C1E83]\', \'\\t(No symbol) [0x00007FF71A29670A]\', \'\\t(No symbol) [0x00007FF71A297964]\', \'\\tGetHandleVerifier [0x00007FF71A7B0AAB+3694587]\', \'\\tGetHandleVerifier [0x00007FF71A80728E+4048862]\', \'\\tGetHandleVerifier [0x00007FF71A7FF173+4015811]\', \'\\tGetHandleVerifier [0x00007FF71A4D47D6+695590]\', \'\\t(No symbol) [0x00007FF71A3B0CE8]\', \'\\t(No symbol) [0x00007FF71A3ACF34]\', \'\\t(No symbol) [0x00007FF71A3AD062]\', \'\\t(No symbol) [0x00007FF71A39D3A3]\', \'\\tBaseThreadInitThunk [0x00007FFC8542257D+29]\', \'\\tRtlUserThreadStart [0x00007FFC8678AA58+40]\', \'\'])' a=True devices=<selenium.webdriver.remote.webelement.WebElement (session="89d438d9f6ef458db3eb52056809c5c6", element="C1D1513D000D844EE60F0D0620DAE980_element_83")>
        log.log_message(f"ok")
        # Should try to clos ethe page ans start a new one

    devices_refresh = devices.text.split('\n')
    devices_lost = set(devices_text) - set(devices_refresh)
    if devices_lost:
        print_devices(devices_lost, "Disconnected")
    devices_new = set(devices_refresh) - set(devices_text)
    if devices_new:
        print_devices(devices_new, "Connected")
    devices_text = devices_refresh



print("ok")
