import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import buffer
import config
import forms
import modbus
import registers
import telemetry


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code
        self.closed = False

    def close(self):
        self.closed = True


class FakeRequests(types.ModuleType):
    def __init__(self):
        super().__init__("requests")
        self.calls = []
        self.next = 202

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls.append((url, data, headers))
        if isinstance(self.next, Exception):
            raise self.next
        return FakeResponse(self.next)


fake_requests = FakeRequests()
sys.modules["requests"] = fake_requests
import uplink  # noqa: E402


def response(slave, words, function=3):
    pdu = bytes([slave, function, len(words) * 2])
    for w in words:
        pdu += bytes([w >> 8, w & 0xFF])
    return modbus.with_crc(pdu)


class ModbusTest(unittest.TestCase):
    def test_request_matches_reference_frame(self):
        self.assertEqual(modbus.read_request(1, 0, 10).hex(), "01030000000ac5cd")

    def test_parses_holding_registers(self):
        frame = response(1, [0x1388, 0xFFF6])
        self.assertEqual(modbus.parse_read_response(frame, 1, 2), [5000, 65526])

    def test_rejects_corrupted_frame(self):
        frame = bytearray(response(1, [1, 2]))
        frame[4] ^= 0xFF
        with self.assertRaisesRegex(modbus.ModbusError, "crc"):
            modbus.parse_read_response(bytes(frame), 1, 2)

    def test_reports_device_exception(self):
        frame = modbus.with_crc(bytes([1, 0x83, 2]))
        with self.assertRaisesRegex(modbus.ModbusError, "exception 2"):
            modbus.parse_read_response(frame, 1, 2)

    def test_rejects_reply_from_wrong_slave(self):
        with self.assertRaisesRegex(modbus.ModbusError, "slave"):
            modbus.parse_read_response(response(2, [1]), 1, 1)

    def test_rejects_short_and_truncated_frames(self):
        with self.assertRaises(modbus.ModbusError):
            modbus.parse_read_response(b"\x01\x03", 1, 1)
        with self.assertRaises(modbus.ModbusError):
            modbus.parse_read_response(response(1, [1]), 1, 2)

    def test_signed_conversion(self):
        self.assertEqual(modbus.to_signed(0xFFF6), -10)
        self.assertEqual(modbus.to_signed(10), 10)


class RegisterPlanTest(unittest.TestCase):
    def test_merges_nearby_registers_and_splits_far_ones(self):
        fields = {"a": (100, 1, False), "b": (101, 1, False), "c": (104, 1, False), "d": (200, 1, False)}
        self.assertEqual(registers.blocks(fields, max_gap=4), [(100, 5), (200, 1)])

    def test_caps_block_size(self):
        fields = {str(i): (i, 1, False) for i in range(10)}
        self.assertEqual(registers.blocks(fields, max_gap=4, max_block=4), [(0, 4), (4, 4), (8, 2)])

    def test_default_plan_covers_every_field(self):
        plan = registers.blocks()
        covered = {a for start, n in plan for a in range(start, start + n)}
        for address, _, _ in registers.FIELDS.values():
            self.assertIn(address, covered)


class TelemetryTest(unittest.TestCase):
    FIELDS = {
        "batteryVoltage": (1, 0.01, False),
        "batteryCurrent": (2, 0.1, True),
        "batterySoc": (3, 1, False),
        "batteryStateCode": (4, 1, False),
        "pvPower": (5, 1, False),
    }

    def test_scales_signs_and_names_values(self):
        out = telemetry.decode({1: 5210, 2: 0xFF9C, 3: 87, 4: 2, 5: 1450}, self.FIELDS, {2: "discharging"})
        self.assertEqual(out["batteryVoltage"], 52.1)
        self.assertEqual(out["batteryCurrent"], -10.0)
        self.assertEqual(out["batterySoc"], 87)
        self.assertEqual(out["batteryState"], "discharging")
        self.assertEqual(out["pvPower"], 1450)
        self.assertNotIn("batteryStateCode", out)

    def test_derives_battery_power_when_not_reported(self):
        out = telemetry.decode({1: 5000, 2: 200}, self.FIELDS)
        self.assertEqual(out["batteryPower"], 1000)

    def test_unknown_state_code(self):
        out = telemetry.decode({4: 99}, self.FIELDS, {})
        self.assertEqual(out["batteryState"], "unknown")

    def test_payload_matches_backend_contract(self):
        body = telemetry.payload("FL123", "IVEM5048", {"batterySoc": 80}, "2026-10-29T10:00:00Z")
        self.assertEqual(body["deviceId"], "FL123")
        self.assertEqual(body["telemetry"], {"batterySoc": 80})


class BufferTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp()
        os.close(fd)
        os.remove(self.path)

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_empty_when_file_missing(self):
        self.assertEqual(len(buffer.Buffer(self.path)), 0)

    def test_keeps_order_and_drops_sent_items(self):
        b = buffer.Buffer(self.path)
        for i in range(3):
            b.push({"n": i})
        self.assertEqual(b.peek(2), [{"n": 0}, {"n": 1}])
        b.drop(2)
        self.assertEqual(b.peek(5), [{"n": 2}])

    def test_discards_oldest_when_full(self):
        b = buffer.Buffer(self.path, max_items=3)
        for i in range(5):
            b.push({"n": i})
        self.assertEqual([x["n"] for x in b.peek(10)], [2, 3, 4])

    def test_corrupt_line_is_returned_as_none(self):
        with open(self.path, "w") as f:
            f.write('{"n": 1}\nnot json\n')
        self.assertEqual(buffer.Buffer(self.path).peek(5), [{"n": 1}, None])


class ConfigTest(unittest.TestCase):
    def test_defaults_and_missing_fields(self):
        cfg = config.load(os.path.join(tempfile.gettempdir(), "no-such-gateway-config.json"))
        self.assertEqual(cfg["interval_s"], 10)
        self.assertEqual(config.missing(cfg), ["wifi_ssid", "gateway_token", "device_id"])

    def test_round_trip(self):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            cfg = dict(config.DEFAULTS, wifi_ssid="Shop", gateway_token="7b_x", device_id="FL1")
            config.save(cfg, path)
            self.assertEqual(config.missing(config.load(path)), [])
        finally:
            os.remove(path)


class FormsTest(unittest.TestCase):
    def test_parses_urlencoded_body(self):
        body = "wifi_ssid=My+Shop&wifi_password=p%40ss%26word&device_id=FL%2F01"
        self.assertEqual(
            forms.parse(body),
            {"wifi_ssid": "My Shop", "wifi_password": "p@ss&word", "device_id": "FL/01"},
        )

    def test_tolerates_bad_escape(self):
        self.assertEqual(forms.unquote("100%"), "100%")
        self.assertEqual(forms.unquote("%zz"), "%zz")

    def test_escapes_html(self):
        self.assertEqual(forms.escape('<a href="x">&'), "&lt;a href=&quot;x&quot;&gt;&amp;")


class UplinkTest(unittest.TestCase):
    def setUp(self):
        fake_requests.calls.clear()

    def test_sends_token_header_and_json(self):
        fake_requests.next = 202
        result, code = uplink.send("https://example.test/t", "7b_tok", {"deviceId": "FL1"})
        self.assertEqual((result, code), (uplink.SENT, 202))
        url, data, headers = fake_requests.calls[0]
        self.assertEqual(headers["x-7th-breed-gateway-token"], "7b_tok")
        self.assertIn('"deviceId"', data)

    def test_config_errors_are_not_retried(self):
        for code in (401, 409, 422):
            fake_requests.next = code
            self.assertEqual(uplink.send("u", "t", {})[0], uplink.REJECTED)

    def test_server_and_network_errors_are_retried(self):
        fake_requests.next = 503
        self.assertEqual(uplink.send("u", "t", {})[0], uplink.RETRY)
        fake_requests.next = OSError("no route")
        self.assertEqual(uplink.send("u", "t", {}), (uplink.RETRY, None))


if __name__ == "__main__":
    unittest.main()
