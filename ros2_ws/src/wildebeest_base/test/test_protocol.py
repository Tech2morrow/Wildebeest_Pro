"""Unit tests for the serial framing contract (no ROS installation needed)."""

import json
import math
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).parents[1]))

from wildebeest_base.protocol import (  # noqa: E402
    Frame,
    FrameStreamDecoder,
    ImuTelemetry,
    MAX_FRAME_BYTES,
    OdomTelemetry,
    ProtocolError,
    RangeTelemetry,
    crc16_ccitt_false,
    decode_frame,
    encode_cmd,
    encode_estop,
    encode_frame,
    parse_telemetry,
    validate_controller_boot,
    validate_schema,
)


class ProtocolTests(unittest.TestCase):
    """Verify framing, integrity, schema, bounds, and SI conversion."""

    def test_crc_standard_check_value(self):
        self.assertEqual(crc16_ccitt_false(b'123456789'), 0x29B1)

    def test_exact_command_wire_format(self):
        body = b'CMD,7,250,-500'
        expected = (
            b'@' + body + b'*' + f'{crc16_ccitt_false(body):04X}'.encode() + b'\n'
        )
        self.assertEqual(encode_cmd(7, 0.25, -0.5), expected)
        self.assertEqual(decode_frame(expected), Frame('CMD', 7, ('250', '-500')))

    def test_round_trip_all_host_commands(self):
        self.assertEqual(
            decode_frame(encode_estop(65535, True)),
            Frame('ESTOP', 65535, ('1',)),
        )
        self.assertEqual(decode_frame(encode_frame('PING', 0)), Frame('PING', 0))

    def test_shared_cross_version_vectors(self):
        fixture_path = (
            Path(__file__).resolve().parents[4]
            / 'tests'
            / 'fixtures'
            / 'protocol-v1.json'
        )
        vectors = json.loads(fixture_path.read_text(encoding='utf-8'))
        self.assertEqual(MAX_FRAME_BYTES, vectors['limits']['max_frame_bytes'])
        for vector in vectors['vectors']:
            with self.subTest(frame=vector['frame']):
                frame = validate_schema(decode_frame(vector['frame'].encode('ascii')))
                self.assertEqual(frame.kind, vector['kind'])
                self.assertEqual(frame.sequence, vector['sequence'])
                self.assertEqual(frame.fields, tuple(vector['fields']))
        for raw in vectors['invalid']:
            with self.subTest(invalid=raw), self.assertRaises(ProtocolError):
                validate_schema(decode_frame(raw.encode('ascii')))

    def test_controller_boot_identity_and_version_are_exact(self):
        boot = decode_frame(
            encode_frame('BOOT', 0, ('WILDEBEEST_BASE', 1))
        )
        self.assertEqual(validate_controller_boot(boot), boot)
        invalid = [
            encode_frame('BOOT', 1, ('WILDEBEEST_BASE', 1)),
            encode_frame('BOOT', 0, ('OTHER_CONTROLLER', 1)),
            encode_frame('BOOT', 0, ('WILDEBEEST_BASE', 2)),
        ]
        for frame in invalid:
            with self.subTest(frame=frame), self.assertRaises(ProtocolError):
                validate_controller_boot(decode_frame(frame))

    def test_malformed_frames_are_rejected(self):
        bad_frames = [
            b'ODOM,1,2*0000\n',
            b'@ODOM,1,2\n',
            b'@ODOM,1,2*ZZZZ\n',
            b'@ODOM,01,2*0000\n',
            b'@bad,1*0000\n',
        ]
        for bad_frame in bad_frames:
            with self.subTest(frame=bad_frame), self.assertRaises(ProtocolError):
                decode_frame(bad_frame)

    def test_checksum_corruption_is_rejected(self):
        frame = bytearray(encode_frame('PING', 42))
        frame[2] ^= 1
        with self.assertRaisesRegex(ProtocolError, 'checksum'):
            decode_frame(bytes(frame))

    def test_stream_decoder_handles_fragmentation_noise_and_recovery(self):
        decoder = FrameStreamDecoder()
        first = encode_frame('PONG', 9)
        second = encode_frame('RANGE', 10, (1500,))
        frames, errors = decoder.feed(b'noise\n' + first[:4])
        self.assertFalse(frames)
        self.assertTrue(errors)
        frames, errors = decoder.feed(first[4:] + second)
        self.assertEqual(
            frames,
            [Frame('PONG', 9), Frame('RANGE', 10, ('1500',))],
        )
        self.assertFalse(errors)

    def test_stream_decoder_resynchronizes_at_mid_frame_start(self):
        decoder = FrameStreamDecoder()
        valid = encode_frame('PONG', 12)
        frames, errors = decoder.feed(b'@BROKEN,1' + valid)
        self.assertEqual(frames, [Frame('PONG', 12)])
        self.assertTrue(errors)

    def test_telemetry_converts_to_si_units(self):
        odom = parse_telemetry(decode_frame(encode_frame(
            'ODOM', 1, (10, -20, 1000, -2000, 8100, 3)
        )))
        self.assertEqual(odom, OdomTelemetry(1, 10, -20, 1.0, -2.0, 8.1, 3))

        imu = parse_telemetry(decode_frame(encode_frame(
            'IMU', 2, (1000, 0, -1000, 180000, 0, -90000)
        )))
        self.assertIsInstance(imu, ImuTelemetry)
        for actual, expected in zip(
            imu.acceleration_m_s2, (9.80665, 0.0, -9.80665)
        ):
            self.assertAlmostEqual(actual, expected)
        for actual, expected in zip(
            imu.angular_velocity_rad_s, (math.pi, 0.0, -math.pi / 2.0)
        ):
            self.assertAlmostEqual(actual, expected)

        distance = parse_telemetry(
            decode_frame(encode_frame('RANGE', 3, (1234,)))
        )
        self.assertEqual(distance, RangeTelemetry(3, 1.234))

    def test_out_of_range_or_wrong_schema_telemetry_is_rejected(self):
        invalid = [
            ('ODOM', (0, 0, 0, 0, 999999, 0)),
            ('IMU', (20000, 0, 0, 0, 0, 0)),
            ('RANGE', (2001,)),
            ('PONG', (1,)),
            ('UNKNOWN', ()),
        ]
        for kind, fields in invalid:
            with self.subTest(kind=kind), self.assertRaises(ProtocolError):
                parse_telemetry(decode_frame(encode_frame(kind, 1, fields)))

    def test_nonfinite_and_out_of_protocol_command_is_rejected(self):
        with self.assertRaises(ProtocolError):
            encode_cmd(0, math.nan, 0.0)
        with self.assertRaises(ProtocolError):
            encode_cmd(0, 0.451, 0.0)


if __name__ == '__main__':
    unittest.main()
