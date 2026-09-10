from __future__ import annotations

from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wildebeest_protocol import (
    Frame,
    MAX_FRAME_BYTES,
    ProtocolError,
    StreamDecoder,
    crc16_ccitt_false,
    decode_frame,
    encode_frame,
    validate_schema,
)


class ProtocolTests(unittest.TestCase):
    def test_standard_crc_vector(self) -> None:
        self.assertEqual(crc16_ccitt_false(b"123456789"), 0x29B1)

    def test_round_trip(self) -> None:
        raw = encode_frame("CMD", 42, 120, -350)
        self.assertEqual(decode_frame(raw), Frame("CMD", 42, ("120", "-350")))

    def test_corruption_is_detected(self) -> None:
        raw = bytearray(encode_frame("PING", 7))
        raw[2] ^= 1
        with self.assertRaises(ProtocolError):
            decode_frame(bytes(raw))

    def test_stream_fragmentation_and_noise(self) -> None:
        decoder = StreamDecoder()
        first = encode_frame("PING", 1)
        second = encode_frame("RANGE", 2, 875)
        self.assertEqual(decoder.feed(b"noise" + first[:5]), [])
        self.assertEqual(decoder.feed(first[5:] + second), [Frame("PING", 1), Frame("RANGE", 2, ("875",))])

    def test_resynchronizes_at_new_start(self) -> None:
        decoder = StreamDecoder()
        frames = decoder.feed(b"@broken" + encode_frame("PONG", 4))
        self.assertEqual(frames, [Frame("PONG", 4)])
        self.assertEqual(decoder.dropped_frames, 1)

    def test_schema_rejects_unsafe_command(self) -> None:
        with self.assertRaises(ProtocolError):
            validate_schema(Frame("CMD", 1, ("900", "0")))

    def test_encoder_rejects_delimiters(self) -> None:
        with self.assertRaises(ProtocolError):
            encode_frame("ERR", 1, "BAD,FIELD")

    def test_shared_interoperability_vectors(self) -> None:
        fixture = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "protocol-v1.json"
        data = json.loads(fixture.read_text(encoding="utf-8"))
        self.assertEqual(MAX_FRAME_BYTES, data["limits"]["max_frame_bytes"])
        for vector in data["vectors"]:
            with self.subTest(frame=vector["frame"]):
                frame = decode_frame(vector["frame"])
                self.assertEqual(frame.kind, vector["kind"])
                self.assertEqual(frame.sequence, vector["sequence"])
                self.assertEqual(list(frame.fields), vector["fields"])
                validate_schema(frame)
        for raw in data["invalid"]:
            with self.subTest(invalid=raw):
                with self.assertRaises(ProtocolError):
                    validate_schema(decode_frame(raw))

    def test_frame_limit_rejects_overflow_and_recovers(self) -> None:
        decoder = StreamDecoder()
        valid = encode_frame("PING", 9)
        self.assertEqual(
            decoder.feed(b"@" + b"X" * MAX_FRAME_BYTES + valid),
            [Frame("PING", 9)],
        )
        self.assertGreaterEqual(decoder.dropped_frames, 1)


if __name__ == "__main__":
    unittest.main()
