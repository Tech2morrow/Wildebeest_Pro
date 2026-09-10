#!/usr/bin/env python3
"""Run every check available without a ROS installation."""

import pathlib
import subprocess
import sys
import unittest


WORKSPACE = pathlib.Path(__file__).resolve().parents[1]


def main():
    static_result = subprocess.run(
        [sys.executable, str(WORKSPACE / "tools" / "static_check.py")],
        cwd=str(WORKSPACE),
        check=False,
    )
    suite = unittest.defaultTestLoader.discover(
        str(WORKSPACE / "src" / "wildebeest_base" / "test"), pattern="test_*.py"
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if static_result.returncode == 0 and result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
