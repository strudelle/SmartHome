# sensor_base.py - common structure for the I2C sensor drivers
#
# Every driver in this project follows the same contract:
#
#     sensor = Driver(i2c, addr=None, **options)   # raises SensorError if unusable
#     values = sensor.read()                       # returns a dict, raises SensorError on failure
#
# Drivers only implement _setup() (configure the chip) and _read() (take a measurement).


class SensorError(Exception):
    """A sensor could not be initialised or read."""


class I2CSensor:
    NAME = "sensor"        # key used in the JSON reply
    DEFAULT_ADDR = 0x00

    def __init__(self, i2c, addr=None):
        self.i2c = i2c
        self.addr = self.DEFAULT_ADDR if addr is None else addr
        if self.addr not in i2c.scan():
            raise SensorError("%s not found on I2C bus at 0x%02x" % (self.NAME, self.addr))
        try:
            self._setup()
        except OSError as e:
            raise SensorError("%s setup failed: %s" % (self.NAME, e))

    def read(self):
        try:
            return self._read()
        except OSError as e:
            raise SensorError("%s I2C read failed: %s" % (self.NAME, e))

    # --- to be implemented by drivers ---
    def _setup(self):
        pass

    def _read(self):
        raise NotImplementedError
