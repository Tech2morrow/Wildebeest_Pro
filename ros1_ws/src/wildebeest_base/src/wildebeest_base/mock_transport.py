"""Deterministic in-process Arduino substitute used for desktop bring-up and CI."""

import math
import time
from typing import List, Optional

from .odometry import DriveGeometry
from .protocol import Frame, decode_frame, encode_frame

FLAG_WATCHDOG = 1 << 0
FLAG_HARD_ESTOP = 1 << 1
FLAG_SOFT_ESTOP = 1 << 2
FLAG_PROTOCOL_ERROR = 1 << 3
FLAG_IMU_FAULT = 1 << 4
FLAG_RANGE_TIMEOUT = 1 << 5
FLAG_LOW_BATTERY = 1 << 6


class MockMcuTransport:
    """Approximate wheel dynamics while preserving the production wire protocol."""

    def __init__(
        self,
        geometry: DriveGeometry,
        watchdog_s: float = 0.30,
        telemetry_hz: float = 20.0,
        monotonic=time.monotonic,
    ):
        self.geometry = geometry
        self.watchdog_s = float(watchdog_s)
        self.telemetry_period = 1.0 / float(telemetry_hz)
        self.monotonic = monotonic
        self.is_open = False
        self.estopped = False
        self.target_linear = 0.0
        self.target_angular = 0.0
        self.left_rad_s = 0.0
        self.right_rad_s = 0.0
        self.left_ticks_f = 0.0
        self.right_ticks_f = 0.0
        self._last_update: Optional[float] = None
        self._last_emit: Optional[float] = None
        self._last_command: Optional[float] = None
        self._sequence = 0
        self._pending: List[bytes] = []

    def open(self) -> None:
        now = self.monotonic()
        self.is_open = True
        self.estopped = False
        self.target_linear = 0.0
        self.target_angular = 0.0
        self.left_rad_s = 0.0
        self.right_rad_s = 0.0
        self.left_ticks_f = 0.0
        self.right_ticks_f = 0.0
        self._last_command = None
        self._sequence = 0
        self._pending = []
        self._last_update = now
        self._last_emit = now
        self._pending.append(encode_frame("BOOT", 0, "WILDEBEEST_BASE", 1))

    def close(self) -> None:
        self.is_open = False
        self.target_linear = 0.0
        self.target_angular = 0.0

    def write(self, payload: bytes) -> None:
        if not self.is_open:
            raise OSError("mock transport is closed")
        frame = decode_frame(payload)
        now = self.monotonic()
        if frame.kind == "CMD":
            self.target_linear = int(frame.fields[0]) / 1000.0
            self.target_angular = int(frame.fields[1]) / 1000.0
            self._last_command = now
        elif frame.kind == "ESTOP":
            self.estopped = bool(int(frame.fields[0]))
            if self.estopped:
                self.target_linear = 0.0
                self.target_angular = 0.0
        elif frame.kind == "PING":
            self._pending.append(encode_frame("PONG", frame.sequence))

    def _next_sequence(self) -> int:
        result = self._sequence
        self._sequence = (self._sequence + 1) & 0xFFFF
        return result

    def read_lines(self) -> List[bytes]:
        if not self.is_open:
            raise OSError("mock transport is closed")
        now = self.monotonic()
        dt = max(0.0, now - float(self._last_update))
        self._last_update = now

        watchdog = self._last_command is None or now - self._last_command >= self.watchdog_s
        linear = 0.0 if watchdog or self.estopped else self.target_linear
        angular = 0.0 if watchdog or self.estopped else self.target_angular
        left_target = (linear - 0.5 * angular * self.geometry.wheel_separation_m) / self.geometry.wheel_radius_m
        right_target = (linear + 0.5 * angular * self.geometry.wheel_separation_m) / self.geometry.wheel_radius_m
        blend = 1.0 - math.exp(-dt / 0.12) if dt > 0.0 else 0.0
        self.left_rad_s += (left_target - self.left_rad_s) * blend
        self.right_rad_s += (right_target - self.right_rad_s) * blend
        if self.estopped:
            self.left_rad_s = 0.0
            self.right_rad_s = 0.0

        ticks_per_rad = self.geometry.encoder_ticks_per_revolution / (2.0 * math.pi)
        self.left_ticks_f += self.left_rad_s * dt * ticks_per_rad
        self.right_ticks_f += self.right_rad_s * dt * ticks_per_rad

        output = self._pending
        self._pending = []
        if now - float(self._last_emit) >= self.telemetry_period:
            self._last_emit = now
            flags = (FLAG_SOFT_ESTOP if self.estopped else 0) | (FLAG_WATCHDOG if watchdog else 0)
            measured_angular = (
                (self.right_rad_s - self.left_rad_s)
                * self.geometry.wheel_radius_m
                / self.geometry.wheel_separation_m
            )
            output.extend(
                [
                    encode_frame(
                        "ODOM",
                        self._next_sequence(),
                        int(round(self.left_ticks_f)),
                        int(round(self.right_ticks_f)),
                        int(round(self.left_rad_s * 1000.0)),
                        int(round(self.right_rad_s * 1000.0)),
                        7600,
                        flags,
                    ),
                    encode_frame(
                        "IMU",
                        self._next_sequence(),
                        0,
                        0,
                        1000,
                        0,
                        0,
                        int(round(math.degrees(measured_angular) * 1000.0)),
                    ),
                    encode_frame("RANGE", self._next_sequence(), 2000),
                ]
            )
        return output
