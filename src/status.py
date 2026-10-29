from machine import I2C, Pin, Timer

# 100 ms steps per pattern, repeated
PATTERNS = {
    "setup": "10",
    "wifi": "1111100000",
    "inverter": "1010000000",
    "rejected": "1010101000",
    "ok": "1000000000000000000000000000000",
}


class Status:
    def __init__(self, led_pin=2, sda=21, scl=22):
        self.led = Pin(led_pin, Pin.OUT)
        self.pattern = PATTERNS["wifi"]
        self.step = 0
        self.timer = Timer(0)
        self.timer.init(period=100, mode=Timer.PERIODIC, callback=self._tick)
        self.oled = None
        try:
            import ssd1306
            i2c = I2C(0, sda=Pin(sda), scl=Pin(scl))
            if 0x3C in i2c.scan():
                self.oled = ssd1306.SSD1306_I2C(128, 64, i2c)
        except Exception:
            self.oled = None

    def _tick(self, _):
        self.led.value(self.pattern[self.step % len(self.pattern)] == "1")
        self.step += 1

    def set(self, name):
        p = PATTERNS[name]
        if p != self.pattern:
            self.pattern = p
            self.step = 0

    def show(self, state, telemetry=None, backlog=0):
        self.set(state)
        if not self.oled:
            return
        o = self.oled
        o.fill(0)
        o.text("7B GATEWAY " + state.upper()[:5], 0, 0)
        t = telemetry or {}

        def v(key, unit):
            x = t.get(key)
            return "--" if x is None else "%s%s" % (x, unit)

        o.text("SOC  " + v("batterySoc", "%"), 0, 14)
        o.text("BATT " + v("batteryVoltage", "V"), 0, 24)
        o.text("PV   " + v("pvPower", "W"), 0, 34)
        o.text("LOAD " + v("loadPower", "W"), 0, 44)
        o.text("QUEUE %d" % backlog, 0, 56)
        o.show()
