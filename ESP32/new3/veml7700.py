# veml7700.py - MicroPython driver for the Vishay VEML7700 ambient light sensor
# (adaptive range)
import time
import struct
from sensor_base import I2CSensor

_REG_CONF = 0x00
_REG_ALS = 0x04
_SD_BIT = 0x0001                       # config bit 0: 1 = shut down

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
        """Switch to the current range step and restart the measurement cycle.

        Writing new settings while the chip is running is not enough: the cycle
        already in progress finishes with the OLD integration time, and the first
        result mixes old and new settings. Going through shutdown (ALS_SD = 1)
        and back on forces a clean new cycle with the new settings.
        """
        self.gain, self.it = _STEPS[self.step]
        conf = (_GAIN_BITS[self.gain] << 11) | (_IT_BITS[self.it] << 6)
        self._write_reg(_REG_CONF, conf | _SD_BIT)   # shut down: aborts running cycle
        time.sleep_ms(3)
        self._write_reg(_REG_CONF, conf)             # power on: fresh cycle, new settings
        time.sleep_ms(2 * self.it + 50)              # let a full conversion complete

    def _to_lux(self, raw):
        res = 0.0036 * (800 / self.it) * (2 / _GAIN_VAL[self.gain])
        lux = raw * res
        # Vishay correction, only relevant at low gain / high lux
        if self.gain in ("1/4", "1/8") and lux > 1000:
            lux = (6.0135e-13 * lux**4 - 9.3924e-9 * lux**3
                   + 8.1488e-5 * lux**2 + 1.0023 * lux)
        return lux

    def _confirm(self, raw, prev_lux):
        """Safety net after a range change.

        The new reading must be consistent with the lux seen just before the change
        (light does not jump by 40-60% in one second). If it is not, wait one more
        conversion and use that reading instead.
        """
        if prev_lux is None:
            return raw
        lux = self._to_lux(raw)
        if prev_lux * 0.6 <= lux <= prev_lux * 1.6:
            return raw
        time.sleep_ms(self.it + 20)
        return self._read_reg(_REG_ALS)

    def _read_lux(self):
        """Read lux, auto-adjusting range. Also stores self.last_raw."""
        prev_lux = None                   # lux measured just before the last range change
        for _ in range(len(_STEPS)):
            raw = self._confirm(self._read_reg(_REG_ALS), prev_lux)
            prev_lux = None
            new = self.step
            if raw >= 60000 and new < _LAST:
                new += 1                  # near saturation -> less sensitive
            elif raw < 100 and new > 0:
                new -= 1                  # too few counts -> more sensitive
            if new == self.step:
                break
            if raw < 65000:               # a clipped reading says nothing about the real lux
                prev_lux = self._to_lux(raw)
            self.step = new
            self._apply()
        else:
            raw = self._confirm(self._read_reg(_REG_ALS), prev_lux)  # settled after the last change
        self.last_raw = raw
        return self._to_lux(raw)
