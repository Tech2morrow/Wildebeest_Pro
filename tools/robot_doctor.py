#!/usr/bin/env python3
"""Preflight checks for a Wildebeest Pro checkout and its commissioning data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tomllib
import xml.etree.ElementTree as ET


REQUIRED_PATHS = (
    "config/robot.toml",
    "firmware/wildebeest_base/platformio.ini",
    "ros1_ws/src",
    "ros2_ws/src",
    "docs",
)


def check_repository(root: Path) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []

    def add(level: str, check: str, detail: str) -> None:
        results.append({"level": level, "check": check, "detail": detail})

    for relative in REQUIRED_PATHS:
        path = root / relative
        add("pass" if path.exists() else "error", f"path:{relative}",
            "present" if path.exists() else "missing")

    config_path = root / "config/robot.toml"
    if config_path.exists():
        try:
            config = tomllib.loads(config_path.read_text(encoding="utf-8"))
            kin = config["kinematics"]
            if kin["wheel_radius_m"] <= 0 or kin["wheel_separation_m"] <= 0:
                add("error", "geometry", "wheel dimensions must be positive")
            else:
                add("pass", "geometry", "positive wheel dimensions")
            if not kin.get("parameters_verified", False):
                add("warning", "geometry-calibration", "measure radius, separation, and encoder CPR")
            if not config["power"].get("voltage_thresholds_verified", False):
                add("warning", "power-calibration", "verify divider and cell/BMS thresholds")
            if config["serial"]["watchdog_ms"] > 500:
                add("warning", "watchdog", "configured above recommended 500 ms maximum")
            else:
                add("pass", "watchdog", f'{config["serial"]["watchdog_ms"]} ms')
        except (KeyError, OSError, tomllib.TOMLDecodeError) as exc:
            add("error", "configuration", str(exc))

    manifests = sorted(root.glob("ros*_ws/src/**/package.xml"))
    if not manifests:
        add("error", "ros-manifests", "no package.xml files found")
    for manifest in manifests:
        try:
            xml = ET.parse(manifest)
            name = xml.findtext("name") or manifest.parent.name
            add("pass", f"package:{name}", str(manifest.relative_to(root)))
        except ET.ParseError as exc:
            add("error", f"package:{manifest.parent.name}", f"invalid XML: {exc}")

    empty_manifests = [p for p in root.rglob("File_List.txt") if p.stat().st_size == 0]
    if empty_manifests:
        add("warning", "legacy-placeholders", f"{len(empty_manifests)} empty File_List.txt placeholders remain")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", help="emit machine-readable results")
    args = parser.parse_args()
    results = check_repository(args.root.resolve())
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        labels = {"pass": "PASS", "warning": "WARN", "error": "FAIL"}
        for result in results:
            print(f"{labels[result['level']]:4}  {result['check']:<28} {result['detail']}")
        totals = {level: sum(r["level"] == level for r in results) for level in labels}
        print(f"\n{totals['pass']} passed, {totals['warning']} warnings, {totals['error']} failed")
    return 1 if any(result["level"] == "error" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
