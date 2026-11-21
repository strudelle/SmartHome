import socket
import struct
import sys
import time
from libraries.util import LoggerSH

"""
This is light sensor from Mathieu that use the ESP32
"""

HOST = "10.0.0.66"  # might need to be changed depending on router
PORT = 6666
TIMEOUT = 1
# "=" -> native byte order, L -> uint32_t, B -> uint8_t, H -> uint16_t
PACKET_FMT_TX = "=LB"
PACKET_FMT_RX = "=LH"

TOTAL_RX_PACKET_SIZE = struct.calcsize(PACKET_FMT_RX)

SYNC_CODE = 0xAA55AA55  # 32 bit au debut de chaque message

log = LoggerSH(to_console=True, log_file_name=f"luminosity.log")
run_for_ever = True
while run_for_ever:

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            s.settimeout(TIMEOUT)
            # print("connected")
            sys.stdout.flush()

            # send message request
            request = struct.pack(PACKET_FMT_TX, SYNC_CODE, 1)
            s.sendall(request)

            # receive luminosity
            rx_data_raw = s.recv(TOTAL_RX_PACKET_SIZE)
            rx_data = struct.unpack(PACKET_FMT_RX, rx_data_raw)

            if rx_data[0] != SYNC_CODE:
                print("invalid sync code data might be invalid")

            lum = rx_data[1]
            pc_lum = int(lum * 100 / 4095)
            log.log_message(f"luminosity:\t{lum}\t{pc_lum} %")

    except Exception as err:
        error_message = f"{err=}"
        log.log_message(f"{error_message=}")
    time.sleep(60)