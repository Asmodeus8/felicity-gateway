# Register map for the inverter's RS-485 port.
# Addresses differ between Felicity models and firmware versions: check them against
# the Modbus protocol document for your unit before deploying.

SLAVE_ID = 1
BAUD_RATE = 9600

# name: (address, scale, signed)
FIELDS = {
    "batteryVoltage": (0x1108, 0.01, False),
    "batteryCurrent": (0x1109, 0.1, True),
    "batteryPower": (0x110A, 1, True),
    "batterySoc": (0x110B, 1, False),
    "batteryStateCode": (0x110C, 1, False),
    "pvVoltage": (0x1120, 0.1, False),
    "pvPower": (0x1121, 1, False),
    "gridVoltage": (0x1130, 0.1, False),
    "gridPower": (0x1131, 1, True),
    "loadVoltage": (0x1140, 0.1, False),
    "loadPower": (0x1141, 1, False),
    "faultCode": (0x1150, 1, False),
    "warningCode": (0x1151, 1, False),
}

BATTERY_STATES = {
    0: "standby",
    1: "charging",
    2: "discharging",
    3: "full",
}

# Gaps up to this many registers are read through rather than split into a second request.
MAX_GAP = 4
MAX_BLOCK = 60


def blocks(fields=FIELDS, max_gap=MAX_GAP, max_block=MAX_BLOCK):
    addresses = sorted(set(a for a, _, _ in fields.values()))
    out = []
    for a in addresses:
        if out:
            start, count = out[-1]
            end = start + count
            if a < end + max_gap and a - start + 1 <= max_block:
                out[-1] = (start, a - start + 1)
                continue
        out.append((a, 1))
    return out
