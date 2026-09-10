"""Dependency-free tests for the simulation command watchdog."""

from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).parents[1]))

from wildebeest_gz.gate import SafetyTwistGate  # noqa: E402


class SafetyTwistGateTests(unittest.TestCase):
    def test_starts_and_times_out_to_zero(self):
        gate = SafetyTwistGate(timeout_s=0.25)
        self.assertEqual(gate.output(1.0), (0.0, 0.0))
        self.assertTrue(gate.receive(0.2, -0.3, 1.0))
        self.assertEqual(gate.output(1.2), (0.2, -0.3))
        self.assertEqual(gate.output(1.251), (0.0, 0.0))

    def test_estop_release_requires_fresh_command(self):
        gate = SafetyTwistGate()
        gate.receive(0.3, 0.4, 2.0)
        gate.set_estop(True)
        self.assertFalse(gate.receive(0.2, 0.1, 2.1))
        gate.set_estop(False)
        self.assertEqual(gate.output(2.2), (0.0, 0.0))
        gate.receive(-0.1, 0.2, 2.3)
        self.assertEqual(gate.output(2.3), (-0.1, 0.2))

    def test_clamps_and_fails_closed_on_time_reversal(self):
        gate = SafetyTwistGate()
        gate.receive(9.0, -9.0, 5.0)
        self.assertEqual(gate.output(5.0), (0.45, -1.8))
        self.assertEqual(gate.output(4.9), (0.0, 0.0))

    def test_rejects_unsafe_configuration_and_nonfinite_command(self):
        for kwargs in (
            {'timeout_s': 0.0},
            {'timeout_s': float('nan')},
            {'max_linear_m_s': -1.0},
            {'max_angular_rad_s': float('inf')},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                SafetyTwistGate(**kwargs)
        gate = SafetyTwistGate()
        self.assertFalse(gate.receive(float('nan'), 0.0, 1.0))
        self.assertEqual(gate.output(1.0), (0.0, 0.0))


if __name__ == '__main__':
    unittest.main()
