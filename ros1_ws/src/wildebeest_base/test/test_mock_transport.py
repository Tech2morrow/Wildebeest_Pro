#!/usr/bin/env python3
import pathlib
import sys
import unittest

PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT / "src"))

from wildebeest_base.mock_transport import (  # noqa: E402
    FLAG_SOFT_ESTOP,
    FLAG_WATCHDOG,
    MockMcuTransport,
)
from wildebeest_base.odometry import DriveGeometry  # noqa: E402
from wildebeest_base.protocol import decode_frame, encode_frame  # noqa: E402


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class MockTransportTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        geometry = DriveGeometry(0.033622, 0.121843, 600)
        self.transport = MockMcuTransport(geometry, monotonic=self.clock)
        self.transport.open()

    def _odom(self, lines):
        return [decode_frame(line) for line in lines if decode_frame(line).kind == "ODOM"][-1]

    def test_boot_ping_motion_and_watchdog_use_wire_protocol(self):
        boot = decode_frame(self.transport.read_lines()[0])
        self.assertEqual((boot.kind, boot.fields), ("BOOT", ("WILDEBEEST_BASE", "1")))
        self.transport.write(encode_frame("PING", 22))
        pong = decode_frame(self.transport.read_lines()[0])
        self.assertEqual((pong.kind, pong.sequence), ("PONG", 22))

        self.transport.write(encode_frame("CMD", 1, 250, 0))
        self.clock.advance(0.15)
        moving = self._odom(self.transport.read_lines())
        self.assertGreater(int(moving.fields[0]), 0)
        self.assertFalse(int(moving.fields[5]) & FLAG_WATCHDOG)

        self.clock.advance(0.31)
        stopped = self._odom(self.transport.read_lines())
        self.assertTrue(int(stopped.fields[5]) & FLAG_WATCHDOG)

    def test_estop_latches_and_is_reported(self):
        self.transport.read_lines()
        self.transport.write(encode_frame("CMD", 1, 200, 0))
        self.transport.write(encode_frame("ESTOP", 2, 1))
        self.clock.advance(0.10)
        odom = self._odom(self.transport.read_lines())
        self.assertTrue(int(odom.fields[5]) & FLAG_SOFT_ESTOP)
        self.assertEqual(int(odom.fields[2]), 0)
        self.assertEqual(int(odom.fields[3]), 0)

    def test_estop_release_does_not_restore_the_previous_target(self):
        self.transport.read_lines()
        self.transport.write(encode_frame("CMD", 1, 200, 0))
        self.clock.advance(0.10)
        moving_speed = int(self._odom(self.transport.read_lines()).fields[2])
        self.assertGreater(moving_speed, 0)

        self.transport.write(encode_frame("ESTOP", 2, 1))
        self.transport.write(encode_frame("ESTOP", 3, 0))
        self.clock.advance(0.10)
        released = self._odom(self.transport.read_lines())
        self.assertEqual(self.transport.target_linear, 0.0)
        self.assertEqual(self.transport.target_angular, 0.0)
        self.assertLess(abs(int(released.fields[2])), moving_speed)
        self.assertLess(abs(int(released.fields[3])), moving_speed)

        self.transport.write(encode_frame("CMD", 4, 200, 0))
        self.clock.advance(0.10)
        fresh = self._odom(self.transport.read_lines())
        self.assertGreater(int(fresh.fields[2]), 0)


if __name__ == "__main__":
    unittest.main()
