"""Deterministic tests for the mock firmware plant and safety behavior."""

from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).parents[1]))

from wildebeest_base.mock_controller import MockController  # noqa: E402
from wildebeest_base.protocol import (  # noqa: E402
    decode_frame,
    encode_cmd,
    encode_estop,
    Frame,
    FrameStreamDecoder,
    OdomTelemetry,
    parse_telemetry,
)
from wildebeest_base.transport import MockTransport  # noqa: E402


def telemetry_from(controller):
    frames, errors = FrameStreamDecoder().feed(controller.drain())
    if errors:
        raise AssertionError(errors)
    return [parse_telemetry(frame) for frame in frames]


class MockControllerTests(unittest.TestCase):
    """Verify the model's kinematics and independent safety states."""

    def test_forward_command_moves_both_encoders(self):
        controller = MockController(telemetry_rate_hz=10.0)
        controller.handle_frame(decode_frame(encode_cmd(1, 0.2, 0.0)))
        controller.advance(0.4)
        odom = [
            item for item in telemetry_from(controller)
            if isinstance(item, OdomTelemetry)
        ]
        self.assertTrue(odom)
        self.assertGreater(odom[-1].left_ticks, 0)
        self.assertGreater(odom[-1].right_ticks, 0)
        self.assertAlmostEqual(odom[-1].left_rad_s, odom[-1].right_rad_s)

    def test_watchdog_decelerates_to_stop_and_sets_flag(self):
        controller = MockController(telemetry_rate_hz=20.0, command_timeout_s=0.2)
        controller.handle_frame(decode_frame(encode_cmd(1, 0.3, 0.0)))
        controller.advance(0.1)
        self.assertGreater(max(controller.wheel_velocities), 0.0)
        controller.advance(1.0)
        for velocity in controller.wheel_velocities:
            self.assertAlmostEqual(velocity, 0.0)
        odom = [
            item for item in telemetry_from(controller)
            if isinstance(item, OdomTelemetry)
        ]
        self.assertTrue(odom[-1].flags & MockController.FLAG_WATCHDOG)

    def test_estop_is_latched_until_explicit_release(self):
        controller = MockController(telemetry_rate_hz=10.0)
        controller.handle_frame(decode_frame(encode_estop(1, True)))
        controller.handle_frame(decode_frame(encode_cmd(2, 0.4, 0.0)))
        controller.advance(0.2)
        self.assertEqual(controller.wheel_velocities, (0.0, 0.0))
        controller.handle_frame(decode_frame(encode_estop(3, False)))
        controller.advance(0.1)
        self.assertEqual(controller.wheel_velocities, (0.0, 0.0))
        controller.handle_frame(decode_frame(encode_cmd(4, 0.4, 0.0)))
        controller.advance(0.1)
        self.assertGreater(max(controller.wheel_velocities), 0.0)

    def test_ping_echoes_sequence(self):
        controller = MockController()
        controller.handle_frame(Frame('PING', 31337))
        frames, errors = FrameStreamDecoder().feed(controller.drain())
        self.assertFalse(errors)
        self.assertEqual(frames, [Frame('PONG', 31337)])

    def test_transport_preserves_boot_announcement(self):
        transport = MockTransport()
        transport.open()
        first = transport.read(maximum_bytes=5)
        remainder = transport.read()
        frames, errors = FrameStreamDecoder().feed(first + remainder)
        transport.close()
        self.assertFalse(errors)
        boot = [frame for frame in frames if frame.kind == 'BOOT']
        self.assertEqual(boot, [Frame('BOOT', 0, ('WILDEBEEST_BASE', '1'))])

    def test_cad_nominal_skid_steer_geometry(self):
        controller = MockController()
        self.assertAlmostEqual(controller.wheel_radius_m, 0.033622)
        self.assertAlmostEqual(controller.wheel_separation_m, 0.121843)


if __name__ == '__main__':
    unittest.main()
