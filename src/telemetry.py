from modbus import to_signed
from registers import FIELDS, BATTERY_STATES


def decode(values, fields=FIELDS, states=BATTERY_STATES):
    out = {}
    for name, (address, scale, signed) in fields.items():
        raw = values.get(address)
        if raw is None:
            continue
        if signed:
            raw = to_signed(raw)
        v = raw * scale
        out[name] = round(v, 2) if isinstance(v, float) else v

    code = out.pop("batteryStateCode", None)
    if code is not None:
        out["batteryState"] = states.get(int(code), "unknown")

    if "batteryPower" not in out and "batteryVoltage" in out and "batteryCurrent" in out:
        out["batteryPower"] = round(out["batteryVoltage"] * out["batteryCurrent"])
    return out


def payload(device_id, model, telemetry, sampled_at):
    return {
        "deviceId": device_id,
        "model": model,
        "sampledAt": sampled_at,
        "telemetry": telemetry,
    }
