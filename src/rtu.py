import time
from modbus import ModbusError, parse_read_response, read_request, response_length


class RtuMaster:
    """Modbus RTU master on a half-duplex RS-485 transceiver (MAX485 DE and RE tied to one pin)."""

    def __init__(self, uart, de, baud, timeout_ms=300, retries=2):
        self.uart = uart
        self.de = de
        self.timeout_ms = timeout_ms
        self.retries = retries
        self.char_us = 11 * 1000000 // baud + 1
        de.value(0)

    def _exchange(self, request, expected):
        while self.uart.any():
            self.uart.read()
        self.de.value(1)
        self.uart.write(request)
        try:
            self.uart.flush()
        except AttributeError:
            time.sleep_us(self.char_us * len(request))
        self.de.value(0)

        frame = b""
        deadline = time.ticks_add(time.ticks_ms(), self.timeout_ms)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            n = self.uart.any()
            if n:
                frame += self.uart.read(n)
                if len(frame) >= expected or (len(frame) >= 5 and frame[1] & 0x80):
                    break
            else:
                time.sleep_ms(2)
        return frame

    def read(self, slave, address, count):
        request = read_request(slave, address, count)
        error = None
        for _ in range(self.retries + 1):
            frame = self._exchange(request, response_length(count))
            try:
                return parse_read_response(frame, slave, count)
            except ModbusError as e:
                error = e
                time.sleep_ms(50)
        raise error

    def read_blocks(self, slave, blocks):
        values = {}
        for start, count in blocks:
            for i, v in enumerate(self.read(slave, start, count)):
                values[start + i] = v
            time.sleep_ms(20)
        return values
