"""Source-level regressions for safety paths that require a ROS runtime."""

from pathlib import Path
import unittest


SOURCE = (
    Path(__file__).resolve().parents[1]
    / 'wildebeest_base'
    / 'serial_bridge_node.py'
).read_text(encoding='utf-8')


def between(start: str, end: str) -> str:
    begin = SOURCE.index(start)
    return SOURCE[begin:SOURCE.index(end, begin)]


class FailClosedContractTests(unittest.TestCase):
    def test_protocol_error_telemetry_invalidates_controller(self):
        odom_branch = between(
            'if isinstance(telemetry, OdomTelemetry):',
            'elif isinstance(telemetry, ImuTelemetry):',
        )
        self.assertIn('FLAG_PROTOCOL_ERROR', odom_branch)
        self.assertIn('self._invalidate_controller(', odom_branch)

    def test_controller_error_frame_invalidates_controller(self):
        error_branch = between(
            "telemetry.kind == 'ERR':",
            'else:\n            self._unknown_frames',
        )
        self.assertIn('self._invalidate_controller(', error_branch)

    def test_invalidation_closes_and_latches_every_motion_gate(self):
        invalidation = between(
            'def _invalidate_controller(',
            'def _handle_transport_error(',
        )
        for fragment in (
            'self._transport.close()',
            'self._controller_ready = False',
            'self._host_estop_latched = True',
            'self._estopped = True',
            'self._last_command_s = None',
            'self._command_timed_out = True',
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, invalidation)


if __name__ == '__main__':
    unittest.main()
