import time

import machine
import network
from machine import UART, WDT, Pin

import config
import portal
import uplink
from buffer import Buffer
from registers import BAUD_RATE, SLAVE_ID, blocks
from rtu import RtuMaster
from status import Status
from telemetry import decode, payload

SETUP_PIN = 0
LED_PIN = 2
DE_PIN = 4
UART_TX = 17
UART_RX = 16

WDT_MS = 30000
WIFI_TIMEOUT_S = 20
WIFI_GIVE_UP_S = 600
FLUSH_BATCH = 5


def connect_wifi(sta, cfg, wdt):
    if sta.isconnected():
        return True
    sta.connect(cfg["wifi_ssid"], cfg["wifi_password"])
    deadline = time.time() + WIFI_TIMEOUT_S
    while time.time() < deadline:
        wdt.feed()
        if sta.isconnected():
            return True
        time.sleep_ms(250)
    sta.disconnect()
    return False


def sync_clock():
    try:
        import ntptime
        ntptime.settime()
        return True
    except Exception:
        return False


def iso_now():
    y, mo, d, h, mi, s = time.gmtime()[:6]
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (y, mo, d, h, mi, s)


def flush(buf, cfg, wdt):
    while len(buf):
        batch = buf.peek(FLUSH_BATCH)
        done = 0
        for body in batch:
            wdt.feed()
            if body is None:
                done += 1
                continue
            result, _ = uplink.send(cfg["api_url"], cfg["gateway_token"], body)
            if result == uplink.RETRY:
                buf.drop(done)
                return False
            done += 1
        buf.drop(done)
    return True


def run():
    cfg = config.load()
    led = Status(LED_PIN)
    if config.missing(cfg) or Pin(SETUP_PIN, Pin.IN, Pin.PULL_UP).value() == 0:
        portal.run(cfg, led)

    wdt = WDT(timeout=WDT_MS)
    uart = UART(2, baudrate=BAUD_RATE, tx=UART_TX, rx=UART_RX, bits=8, parity=None, stop=1, timeout=0)
    rtu = RtuMaster(uart, Pin(DE_PIN, Pin.OUT), BAUD_RATE)
    buf = Buffer("buffer.jsonl")
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    plan = blocks()
    interval_ms = int(cfg["interval_s"]) * 1000
    offline_since = None
    clock_ok = False

    while True:
        started = time.ticks_ms()
        wdt.feed()

        online = connect_wifi(sta, cfg, wdt)
        if online:
            offline_since = None
            if not clock_ok:
                clock_ok = sync_clock()
        else:
            offline_since = offline_since or time.time()
            if time.time() - offline_since > WIFI_GIVE_UP_S:
                machine.reset()

        telemetry = None
        state = "ok"
        try:
            telemetry = decode(rtu.read_blocks(SLAVE_ID, plan))
        except Exception:
            state = "inverter"

        if telemetry is not None:
            body = payload(cfg["device_id"], cfg["model"], telemetry, iso_now() if clock_ok else None)
            if online and flush(buf, cfg, wdt):
                result, _ = uplink.send(cfg["api_url"], cfg["gateway_token"], body)
                if result == uplink.RETRY:
                    buf.push(body)
                    state = "wifi"
                elif result == uplink.REJECTED:
                    state = "rejected"
            else:
                buf.push(body)
                state = "wifi"
        elif not online:
            state = "wifi"

        led.show(state, telemetry, len(buf))

        while time.ticks_diff(time.ticks_ms(), started) < interval_ms:
            wdt.feed()
            time.sleep_ms(200)


run()
