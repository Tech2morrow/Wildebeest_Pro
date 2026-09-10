from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
FIRMWARE = ROOT / "firmware" / "wildebeest_base"


def integer_constant(source: str, name: str) -> int:
    match = re.search(
        rf"constexpr\s+[^;=]+\s+{re.escape(name)}\s*=\s*(\d+)",
        source,
    )
    if match is None:
        raise AssertionError(f"missing integer firmware constant {name}")
    return int(match.group(1))


class FirmwareContractTests(unittest.TestCase):
    def test_protocol_limits_match_shared_fixture(self) -> None:
        fixture = json.loads(
            (ROOT / "tests" / "fixtures" / "protocol-v1.json").read_text(
                encoding="utf-8"
            )
        )
        protocol = (FIRMWARE / "include" / "Protocol.h").read_text(encoding="utf-8")
        config = (FIRMWARE / "include" / "Config.h").read_text(encoding="utf-8")
        main = (FIRMWARE / "src" / "main.cpp").read_text(encoding="utf-8")

        self.assertEqual(
            integer_constant(protocol, "MAX_FRAME_BYTES"),
            fixture["limits"]["max_frame_bytes"],
        )
        self.assertEqual(integer_constant(config, "MAX_LINEAR_MM_S"), 450)
        self.assertEqual(integer_constant(config, "MAX_ANGULAR_MRAD_S"), 1800)
        self.assertIn("constrain(echoUs * 10UL / 58UL, 20UL, 2000UL)", main)

    def test_receiver_resynchronizes_on_each_start_marker(self) -> None:
        protocol = (FIRMWARE / "include" / "Protocol.h").read_text(encoding="utf-8")
        start = protocol.index("if (byte == '@')")
        resync_block = protocol[start:protocol.index("if (length_ == 0)", start)]
        for fragment in (
            "length_ = 0",
            "overflow_ = false",
            "ready_ = false",
            "buffer_[length_++] = byte",
        ):
            self.assertIn(fragment, resync_block)

    def test_low_voltage_stop_is_separate_from_warning(self) -> None:
        config = (FIRMWARE / "include" / "Config.h").read_text(encoding="utf-8")
        main = (FIRMWARE / "src" / "main.cpp").read_text(encoding="utf-8")
        self.assertEqual(integer_constant(config, "BATTERY_STOP_MV"), 6600)
        self.assertEqual(integer_constant(config, "BATTERY_STOP_HYSTERESIS_MV"), 150)
        self.assertIn("constexpr bool ENABLE_LOW_VOLTAGE_MOTOR_STOP = false", config)
        self.assertIn("wb::nextLowVoltageMotorStop", main)
        motion = main[main.index("bool motionEnabled()"):main.index("void updateControl")]
        self.assertIn("lowVoltageMotorStopActive", motion)
        self.assertNotIn("FLAG_LOW_BATTERY", motion)


if __name__ == "__main__":
    unittest.main()
