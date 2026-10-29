import socket
import time

import machine
import network

import config
from forms import escape, parse

AP_PASSWORD = "7thbreed-setup"

FIELDS = (
    ("wifi_ssid", "Wi-Fi network", "text"),
    ("wifi_password", "Wi-Fi password", "password"),
    ("gateway_token", "Gateway token", "password"),
    ("device_id", "Inverter serial number", "text"),
    ("api_url", "Telemetry URL", "text"),
    ("interval_s", "Send every (seconds)", "number"),
)


def page(cfg, note=""):
    rows = "".join(
        '<label>%s<input name="%s" type="%s" value="%s"></label>'
        % (label, key, kind, "" if kind == "password" else escape(cfg.get(key, "")))
        for key, label, kind in FIELDS
    )
    return (
        "<!doctype html><meta name=viewport content='width=device-width'>"
        "<title>Gateway setup</title><style>body{font:16px sans-serif;max-width:420px;margin:24px auto;padding:0 16px}"
        "label{display:block;margin:12px 0}input{display:block;width:100%;padding:8px;box-sizing:border-box}"
        "button{padding:10px 18px}</style><h2>Gateway setup</h2><p>" + note + "</p>"
        "<form method=post action=/save>" + rows + "<button>Save and restart</button></form>"
    )


def _read_request(conn):
    data = b""
    while b"\r\n\r\n" not in data and len(data) < 4096:
        chunk = conn.recv(512)
        if not chunk:
            break
        data += chunk
    head, _, body = data.partition(b"\r\n\r\n")
    lines = head.decode().split("\r\n")
    method, path = (lines[0].split(" ") + ["", ""])[:2]
    length = 0
    for line in lines[1:]:
        if line.lower().startswith("content-length:"):
            length = int(line.split(":", 1)[1])
    while len(body) < length:
        chunk = conn.recv(512)
        if not chunk:
            break
        body += chunk
    return method, path, body.decode()


def _reply(conn, html):
    conn.send(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n")
    conn.send(html.encode())


def run(cfg, status=None):
    if status:
        status.set("setup")
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    suffix = "".join("%02X" % b for b in ap.config("mac")[-2:])
    ap.config(essid="7B-Gateway-" + suffix, password=AP_PASSWORD, authmode=network.AUTH_WPA2_PSK)

    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 80))
    s.listen(2)
    missing = config.missing(cfg)
    note = "Missing: " + ", ".join(missing) if missing else "Connect to this gateway's Wi-Fi and fill in the form."

    while True:
        conn, _ = s.accept()
        try:
            method, path, body = _read_request(conn)
            if method == "POST" and path == "/save":
                form = parse(body)
                for key, _, kind in FIELDS:
                    value = form.get(key, "").strip()
                    if kind == "password" and not value:
                        continue
                    if kind == "number":
                        try:
                            value = max(5, int(value))
                        except ValueError:
                            continue
                    cfg[key] = value
                config.save(cfg)
                _reply(conn, "<p>Saved. The gateway is restarting.</p>")
                conn.close()
                time.sleep(1)
                machine.reset()
            _reply(conn, page(cfg, note))
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass
