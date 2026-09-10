#!/usr/bin/env python3
import math
import pathlib
import sys
import unittest

PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT / "src"))

from wildebeest_base.odometry import (  # noqa: E402
    DifferentialOdometry,
    DriveGeometry,
    OdometryDiscontinuity,
    signed_int32_delta,
)


class OdometryTests(unittest.TestCase):
    def setUp(self):
        self.geometry = DriveGeometry(0.033622, 0.121843, 600)
        self.odometry = DifferentialOdometry(self.geometry)

    def test_one_wheel_revolution_moves_one_circumference(self):
        self.odometry.update(0, 0, 1.0)
        sample = self.odometry.update(600, 600, 2.0)
        expected = 2.0 * math.pi * self.geometry.wheel_radius_m
        self.assertAlmostEqual(sample.x_m, expected, places=9)
        self.assertAlmostEqual(sample.y_m, 0.0, places=9)
        self.assertAlmostEqual(sample.linear_m_s, expected, places=9)
        self.assertAlmostEqual(sample.yaw_rad, 0.0, places=9)

    def test_in_place_turn_has_no_translation(self):
        self.odometry.update(0, 0, 0.0)
        sample = self.odometry.update(-300, 300, 1.0)
        expected_yaw = 2.0 * math.pi * self.geometry.wheel_radius_m / self.geometry.wheel_separation_m
        self.assertAlmostEqual(sample.x_m, 0.0, places=9)
        self.assertAlmostEqual(sample.y_m, 0.0, places=9)
        self.assertAlmostEqual(sample.yaw_rad, expected_yaw, places=9)

    def test_int32_counter_rollover(self):
        self.assertEqual(signed_int32_delta(-2147483648, 2147483647), 1)
        self.assertEqual(signed_int32_delta(2147483647, -2147483648), -1)

    def test_invalid_geometry_is_rejected(self):
        with self.assertRaises(ValueError):
            DriveGeometry(0.0, 0.121843, 600)
        with self.assertRaises(ValueError):
            DriveGeometry(0.033622, 0.0, 600)
        with self.assertRaises(ValueError):
            DriveGeometry(0.033622, 0.121843, 0)

    def test_implausible_jump_is_rejected_before_pose_changes(self):
        odometry = DifferentialOdometry(self.geometry, maximum_tick_delta=100)
        odometry.update(0, 0, 0.0)
        with self.assertRaises(OdometryDiscontinuity):
            odometry.update(101, 0, 1.0)
        self.assertEqual(odometry.x_m, 0.0)
        self.assertEqual(odometry.y_m, 0.0)


if __name__ == "__main__":
    unittest.main()
