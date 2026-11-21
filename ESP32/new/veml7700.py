# veml7700.py - MicroPython driver for the Vishay VEML7700 ambient light sensor
# (adaptive range)
import time
import struct
from sensor_base import I2CSensor

_REG_CONF = 0x00
_REG_ALS = 0x04

_GAIN_BITS = {"2": 0b01, "1": 0b00, "1/4": 0b11, "1/8": 0b10}
_GAIN_VAL = {"2": 2.0, "1": 1.0, "1/4": 0.25, "1/8": 0.125}
_IT_BITS = {25: 0b1100, 50: 0b1000, 100: 0b0000,
            200: 0b0001, 400: 0b0010, 800: 0b0011}

# Range steps, most sensitive first (each step is 2x-16x less sensitive)
_STEPS = (("2", 800), ("1", 400), ("1/4", 100), ("1/8", 100), ("1/8", 25))
_LAST = len(_STEPS) - 1


class VEML7700(I2CSensor):
    NAME = "veml7700"
    DEFAULT_ADDR = 0x10

    # --- I2CSensor contract ---
    def _setup(self):
        self.step = 0                     # start at max sensitivity
        self.last_raw = 0
        self._apply()

    def _read(self):
        lux = self._read_lux()
        return {"lux": round(lux, 2), "raw": self.last_raw,
                "gain": self.gain, "it": self.it}

    # --- low level ---
    def _write_reg(self, reg, value):
        self.i2c.writeto_mem(self.addr, reg, struct.pack("<H", value))

    def _read_reg(self, reg):
        return struct.unpack("<H", self.i2c.readfrom_mem(self.addr, reg, 2))[0]

    def _apply(self):
        self.gain, self.it = _STEPS[self.step]
        conf = (_GAIN_BITS[self.gain] << 11) | (_IT_BITS[self.it] << 6)
        self._write_reg(_REG_CONF, conf)  # bit 0 = 0 -> sensor on
        time.sleep_ms(2 * self.it + 50)   # let a fresh conversion complete

    def _to_lux(self, raw):
        res = 0.0036 * (800 / self.it) * (2 / _GAIN_VAL[self.gain])
        lux = raw * res
        # Vishay correction, only relevant at low gain / high lux
        if self.gain in ("1/4", "1/8") and lux > 1000:
            lux = (6.0135e-13 * lux**4 - 9.3924e-9 * lux**3
                   + 8.1488e-5 * lux**2 + 1.0023 * lux)
        return lux

    def _read_lux(self):
        """Read lux, auto-adjusting range. Also stores self.last_raw."""
        for _ in range(len(_STEPS)):
            raw = self._read_reg(_REG_ALS)
            new = self.step
            if raw >= 60000 and new < _LAST:
                new += 1                  # near saturation -> less sensitive
            elif raw < 100 and new > 0:
                new -= 1                  # too few counts -> more sensitive
            if new == self.step:
                break
            self.step = new
            self._apply()
        else:
            raw = self._read_reg(_REG_ALS)  # settled after the last change
        self.last_raw = raw
        return self._to_lux(raw)
