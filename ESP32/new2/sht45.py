# sht45.py - MicroPython driver for the Sensirion SHT45 temperature/humidity sensor
# (SHT4x family: different commands from the SHT31)
import time
from sensor_base import I2CSensor, SensorError

_CMD_MEASURE_HIGH = b"\xFD"       # single shot, high precision (max conversion ~8.3 ms)
_CMD_SOFT_RESET = b"\x94"


def _crc8(data):
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


class SHT45(I2CSensor):
    NAME = "sht45"
    DEFAULT_ADDR = 0x44               # SHT45-AD1B; other SHT4x variants use 0x45 / 0x46

    def __init__(self, i2c, addr=None, temp_offset=0.0):
        # temp_offset: degrees C added to the reading (calibration / self-heating fix)
        self.temp_offset = temp_offset
        super().__init__(i2c, addr)

    # --- I2CSensor contract ---
    def _setup(self):
        self.i2c.writeto(self.addr, _CMD_SOFT_RESET)
        time.sleep_ms(5)              # reset takes at most 1 ms

    def _read(self):
        self.i2c.writeto(self.addr, _CMD_MEASURE_HIGH)
        time.sleep_ms(10)
        data = self.i2c.readfrom(self.addr, 6)

        if _crc8(data[0:2]) != data[2] or _crc8(data[3:5]) != data[5]:
            raise SensorError("sht45 CRC mismatch (noisy bus or bad wiring)")

        raw_t = (data[0] << 8) | data[1]
        raw_h = (data[3] << 8) | data[4]
        temp = -45 + 175 * raw_t / 65535 + self.temp_offset
        hum = max(0.0, min(100.0, -6 + 125 * raw_h / 65535))
        return {"temp_c": round(temp, 2), "humidity": round(hum, 2)}
