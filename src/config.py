try:
    import ujson as json
except ImportError:
    import json

PATH = "config.json"

DEFAULTS = {
    "wifi_ssid": "",
    "wifi_password": "",
    "api_url": "https://backend.7thbreed.com/api/auth/monitor/gateway/felicity/telemetry",
    "gateway_token": "",
    "device_id": "",
    "model": "Felicity Solar inverter",
    "interval_s": 10,
}

REQUIRED = ("wifi_ssid", "api_url", "gateway_token", "device_id")


def load(path=PATH):
    cfg = dict(DEFAULTS)
    try:
        with open(path) as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def save(cfg, path=PATH):
    with open(path, "w") as f:
        json.dump(cfg, f)


def missing(cfg):
    return [k for k in REQUIRED if not str(cfg.get(k, "")).strip()]
