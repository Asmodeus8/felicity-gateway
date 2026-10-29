class ModbusError(Exception):
    pass


def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def with_crc(pdu):
    c = crc16(pdu)
    return bytes(pdu) + bytes([c & 0xFF, c >> 8])


def read_request(slave, address, count, function=3):
    return with_crc(bytes([slave, function, address >> 8, address & 0xFF, count >> 8, count & 0xFF]))


def response_length(count):
    return 5 + 2 * count


def parse_read_response(frame, slave, count, function=3):
    if len(frame) < 5:
        raise ModbusError("short frame (%d bytes)" % len(frame))
    c = crc16(frame[:-2])
    if frame[-2] != c & 0xFF or frame[-1] != c >> 8:
        raise ModbusError("bad crc")
    if frame[0] != slave:
        raise ModbusError("reply from slave %d, expected %d" % (frame[0], slave))
    if frame[1] == function | 0x80:
        raise ModbusError("device exception %d" % frame[2])
    if frame[1] != function:
        raise ModbusError("unexpected function %d" % frame[1])
    n = frame[2]
    if n != count * 2 or len(frame) != 5 + n:
        raise ModbusError("bad byte count")
    return [(frame[3 + 2 * i] << 8) | frame[4 + 2 * i] for i in range(count)]


def to_signed(value):
    return value - 0x10000 if value & 0x8000 else value
