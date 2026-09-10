#!/usr/bin/env python3
import json
import pathlib
import sys
import unittest

PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT / "src"))

from wildebeest_base.protocol import (  # noqa: E402
    Frame,
    FrameStreamDecoder,
    MAX_FRAME_BYTES,
    ProtocolError,
    crc16_ccitt_false,
    decode_frame,
    encode_frame,
)


class ProtocolTests(unittest.TestCase):
    def test_standard_crc_check_value(self):
        self.assertEqual(crc16_ccitt_false(b"123456789"), 0x29B1)

    def test_fixed_vectors(self):
        self.assertEqual(encode_frame("PING", 42), b"@PING,42*F43D\n")
        self.assertEqual(encode_frame("CMD", 7, 250, -500), b"@CMD,7,250,-500*6280\n")
        self.assertEqual(
            encode_frame("BOOT", 0, "WILDEBEEST_BASE", 1),
            b"@BOOT,0,WILDEBEEST_BASE,1*6C1C\n",
        )

    def test_round_trip_every_schema(self):
        vectors = (
            ("CMD", 10, (450, -1800)),
            ("PING", 11, ()),
            ("ESTOP", 12, (1,)),
            ("ODOM", 13, (-2147483648, 2147483647, -1000, 1000, 7400, 65)),
            ("IMU", 14, (0, 0, 1000, -100, 200, -300)),
            ("RANGE", 15, (2000,)),
            ("PONG", 16, ()),
            ("BOOT", 0, ("WILDEBEEST_BASE", 1)),
            ("ERR", 17, ("RANGE",)),
        )
        for kind, sequence, fields in vectors:
            with self.subTest(kind=kind):
                self.assertEqual(
                    decode_frame(encode_frame(kind, sequence, *fields)),
                    Frame(kind, sequence, tuple(str(value) for value in fields)),
                )

    def test_shared_cross_version_fixture(self):
        fixture_path = PACKAGE_ROOT.parents[2] / "tests" / "fixtures" / "protocol-v1.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.assertEqual(MAX_FRAME_BYTES, fixture["limits"]["max_frame_bytes"])
        for vector in fixture["vectors"]:
            with self.subTest(frame=vector["frame"]):
                raw = vector["frame"].encode("ascii")
                decoded = decode_frame(raw)
                self.assertEqual(decoded.kind, vector["kind"])
                self.assertEqual(decoded.sequence, vector["sequence"])
                self.assertEqual(list(decoded.fields), vector["fields"])
                self.assertEqual(
                    encode_frame(decoded.kind, decoded.sequence, *decoded.fields), raw
                )
        for invalid in fixture["invalid"]:
            with self.subTest(invalid=invalid), self.assertRaises(ProtocolError):
                decode_frame(invalid.encode("ascii"))

    def test_corruption_is_rejected(self):
        valid = encode_frame("PING", 1)
        corrupted = valid.replace(b"PING", b"PONG")
        with self.assertRaises(ProtocolError):
            decode_frame(corrupted)
        with self.assertRaises(ProtocolError):
            decode_frame(b"@PING,42*+43D\n")

    def test_unsafe_values_and_noncanonical_integers_are_rejected(self):
        for fields in ((451, 0), (0, 1801), ("01", 0), (0, "-0")):
            with self.subTest(fields=fields), self.assertRaises(ProtocolError):
                encode_frame("CMD", 1, *fields)
        with self.assertRaises(ProtocolError):
            encode_frame("RANGE", 1, 2001)
        with self.assertRaises(ProtocolError):
            encode_frame("PING", True)

    def test_stream_decoder_resynchronizes_and_bounds_memory(self):
        decoder = FrameStreamDecoder(maximum_line_bytes=64)
        output = decoder.feed(b"noise" + encode_frame("PING", 3) + encode_frame("PONG", 3))
        self.assertEqual(output, [encode_frame("PING", 3), encode_frame("PONG", 3)])
        decoder.feed(b"@" + b"x" * 100)
        self.assertGreaterEqual(decoder.dropped_lines, 1)
        self.assertEqual(decoder.feed(encode_frame("PING", 4)), [encode_frame("PING", 4)])

    def test_new_start_marker_resynchronizes_mid_frame(self):
        decoder = FrameStreamDecoder()
        valid = encode_frame("PING", 9)
        self.assertEqual(decoder.feed(b"@BROKEN,1" + valid), [valid])
        self.assertEqual(decoder.dropped_lines, 1)


if __name__ == "__main__":
    unittest.main()
