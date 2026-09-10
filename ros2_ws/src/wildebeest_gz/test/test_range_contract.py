"""Dependency-free tests for simulated range normalization."""

import math
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).parents[1]))

from wildebeest_gz.range_contract import normalize_range  # noqa: E402


class RangeContractTests(unittest.TestCase):
    def test_preserves_in_contract_reading(self):
        self.assertEqual(normalize_range(0.75, 0.02, 2.0), 0.75)

    def test_maps_outside_readings_to_ros_sentinels(self):
        self.assertEqual(normalize_range(0.01, 0.02, 2.0), float('-inf'))
        self.assertEqual(normalize_range(2.01, 0.02, 2.0), float('inf'))

    def test_rejects_invalid_values_and_limits(self):
        for arguments in (
            (float('nan'), 0.02, 2.0),
            (0.5, 0.0, 2.0),
            (0.5, 2.0, 1.0),
        ):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                normalize_range(*arguments)

    def test_sentinels_are_infinite(self):
        self.assertTrue(math.isinf(normalize_range(0.0, 0.02, 2.0)))
        self.assertEqual(
            normalize_range(float('-inf'), 0.02, 2.0), float('-inf')
        )
        self.assertEqual(normalize_range(float('inf'), 0.02, 2.0), float('inf'))


if __name__ == '__main__':
    unittest.main()
