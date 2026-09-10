#!/usr/bin/env python3
import pathlib
import sys
import unittest

PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT / "src"))

from wildebeest_base.safety import (  # noqa: E402
    controller_boot_is_supported,
    motion_command_is_ready,
)


class MotionFreshnessTests(unittest.TestCase):
    def test_pre_release_command_is_never_reused(self):
        release_time = 10.10
        self.assertFalse(motion_command_is_ready(10.11, 10.00, release_time, 0.25, True))
        self.assertFalse(
            motion_command_is_ready(10.11, release_time, release_time, 0.25, True)
        )
        self.assertTrue(motion_command_is_ready(10.21, 10.20, release_time, 0.25, True))

    def test_handshake_and_timeout_fail_closed(self):
        self.assertFalse(motion_command_is_ready(1.0, 0.9, None, 0.25, True))
        self.assertFalse(motion_command_is_ready(2.0, 1.5, 1.0, 0.25, True))
        self.assertFalse(motion_command_is_ready(1.0, 1.1, 0.5, 0.25, True))
        self.assertFalse(motion_command_is_ready(1.0, 0.9, 0.5, 0.25, False))

    def test_only_exact_protocol_v1_boot_readies_the_controller(self):
        self.assertTrue(controller_boot_is_supported(0, "WILDEBEEST_BASE", "1"))
        self.assertFalse(controller_boot_is_supported(1, "WILDEBEEST_BASE", "1"))
        self.assertFalse(controller_boot_is_supported(0, "OTHER_BASE", "1"))
        self.assertFalse(controller_boot_is_supported(0, "WILDEBEEST_BASE", "2"))


if __name__ == "__main__":
    unittest.main()
