try:
    import ujson as json
    import urequests as requests
except ImportError:
    import json
    import requests

SENT = "sent"
REJECTED = "rejected"
RETRY = "retry"

# The backend answers these when the token, device ID or payload is wrong.
# Resending will not help, so the reading is dropped and the status shows a config fault.
PERMANENT = (400, 401, 403, 409, 422)


def send(url, token, body, timeout=10):
    try:
        r = requests.post(
            url,
            data=json.dumps(body),
            headers={"Content-Type": "application/json", "x-7th-breed-gateway-token": token},
            timeout=timeout,
        )
    except Exception:
        return RETRY, None
    try:
        code = r.status_code
    finally:
        r.close()
    if 200 <= code < 300:
        return SENT, code
    if code in PERMANENT:
        return REJECTED, code
    return RETRY, code
