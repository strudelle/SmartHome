# sht31.py - minimal MicroPython driver for the Sensirion SHT31
import time

_CMD_MEASURE_HIGH = b"\x24\x00"   # single shot, high repeatability, no clock stretching
_CMD_SOFT_RESET = b"\x30\xA2"
_CMD_HEATER_OFF = b"\x30\x66"


class SHT31:
    def __init__(self, i2c, addr=0x44, temp_offset=0.0):
        """
        addr: 0x44 (ADDR pin low / default) or 0x45 (ADDR pin high)
        temp_offset: degrees C added to the reading (calibration / self-heating fix)
        """
        self.i2c = i2c
        self.addr = addr
        self.temp_offset = temp_offset
        self.reset()

    # --- low level ---
    @staticmethod
    def _crc8(data):
        crc = 0xFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
        return crc

    def reset(self):
        self.i2c.writeto(self.addr, _CMD_SOFT_RESET)
        time.sleep_ms(10)
        self.i2c.writeto(self.addr, _CMD_HEATER_OFF)
        time.sleep_ms(2)

    # --- public ---
    def read(self):
        """Return (temperature_c, humidity_pct). Raises OSError/ValueError on failure."""
        self.i2c.writeto(self.addr, _CMD_MEASURE_HIGH)
        time.sleep_ms(20)                         # max conversion time is ~15 ms
        data = self.i2c.readfrom(self.addr, 6)

        if self._crc8(data[0:2]) != data[2] or self._crc8(data[3:5]) != data[5]:
            raise ValueError("SHT31 CRC mismatch")

        raw_t = (data[0] << 8) | data[1]
        raw_h = (data[3] << 8) | data[4]
        temp = -45 + 175 * raw_t / 65535 + self.temp_offset
        hum = max(0.0, min(100.0, 100 * raw_h / 65535))
        return temp, hum