"""Deterministic Arduino/controller model used by development and tests."""

from collections import deque
import math
from typing import Deque

from .protocol import encode_frame, Frame, ProtocolError


class MockController:
    """A small differential-drive plant implementing the serial contract.

    Time advances only through :meth:`advance`, which keeps unit tests fast and
    deterministic.  It models velocity slew, encoder counts, telemetry cadence,
    a command watchdog, and a latched emergency stop.
    """

    FLAG_WATCHDOG = 1 << 0
    FLAG_HARD_ESTOP = 1 << 1
    FLAG_SOFT_ESTOP = 1 << 2
    FLAG_PROTOCOL_ERROR = 1 << 3
    FLAG_IMU_ERROR = 1 << 4
    FLAG_RANGE_TIMEOUT = 1 << 5
    FLAG_LOW_BATTERY = 1 << 6

    def __init__(
        self,
        wheel_radius_m: float = 0.033622,
        wheel_separation_m: float = 0.121843,
        ticks_per_revolution: int = 600,
        telemetry_rate_hz: float = 30.0,
        command_timeout_s: float = 0.3,
        velocity_slew_rad_s2: float = 25.0,
        max_wheel_rad_s: float = 18.0,
    ) -> None:
        if wheel_radius_m <= 0.0 or wheel_separation_m <= 0.0:
            raise ValueError('wheel geometry must be positive')
        if ticks_per_revolution <= 0 or telemetry_rate_hz <= 0.0:
            raise ValueError('encoder resolution and telemetry rate must be positive')
        if command_timeout_s <= 0.0 or max_wheel_rad_s <= 0.0:
            raise ValueError('watchdog and wheel-speed limit must be positive')
        self.wheel_radius_m = wheel_radius_m
        self.wheel_separation_m = wheel_separation_m
        self.ticks_per_revolution = ticks_per_revolution
        self.telemetry_period_s = 1.0 / telemetry_rate_hz
        self.command_timeout_s = command_timeout_s
        self.velocity_slew_rad_s2 = velocity_slew_rad_s2
        self.max_wheel_rad_s = max_wheel_rad_s
        self.front_range_m = 1.5
        self.battery_v = 8.1

        self.elapsed_s = 0.0
        self._telemetry_accumulator_s = 0.0
        self._time_since_command_s = math.inf
        self._sequence = 0
        self._left_target = 0.0
        self._right_target = 0.0
        self._left_velocity = 0.0
        self._right_velocity = 0.0
        self._left_position = 0.0
        self._right_position = 0.0
        self.estopped = False
        self.watchdog_active = True
        self._queued: Deque[bytes] = deque()

    def handle_frame(self, frame: Frame) -> None:
        """Apply one checksum-verified host command."""
        if frame.kind == 'CMD':
            self._require_fields(frame, 2)
            linear_mm_s = self._integer(frame.fields[0], -450, 450, 'linear_mm_s')
            angular_mrad_s = self._integer(
                frame.fields[1], -1800, 1800, 'angular_mrad_s'
            )
            linear = linear_mm_s / 1000.0
            angular = angular_mrad_s / 1000.0
            left_target = (
                linear - angular * self.wheel_separation_m / 2.0
            ) / self.wheel_radius_m
            right_target = (
                linear + angular * self.wheel_separation_m / 2.0
            ) / self.wheel_radius_m
            peak = max(abs(left_target), abs(right_target))
            scale = min(1.0, self.max_wheel_rad_s / peak) if peak else 1.0
            if self.estopped:
                self._left_target = 0.0
                self._right_target = 0.0
            else:
                self._left_target = left_target * scale
                self._right_target = right_target * scale
            self._time_since_command_s = 0.0
            self.watchdog_active = False
        elif frame.kind == 'PING':
            self._require_fields(frame, 0)
            self._queued.append(encode_frame('PONG', frame.sequence))
        elif frame.kind == 'ESTOP':
            self._require_fields(frame, 1)
            engaged = self._integer(frame.fields[0], 0, 1, 'estop')
            self.estopped = bool(engaged)
            # Both edges invalidate the previous motion request. Releasing an
            # estop therefore requires a new CMD before motion can resume.
            self._left_target = 0.0
            self._right_target = 0.0
        else:
            raise ProtocolError(f'unsupported host command: {frame.kind}')

    def advance(self, duration_s: float) -> None:
        """Advance the model and enqueue any due telemetry."""
        if not math.isfinite(duration_s) or duration_s < 0.0:
            raise ValueError('duration_s must be finite and non-negative')
        if duration_s == 0.0:
            return
        remaining = duration_s
        maximum_step = min(0.01, self.telemetry_period_s)
        while remaining > 1e-12:
            step = min(maximum_step, remaining)
            remaining -= step
            self.elapsed_s += step
            self._telemetry_accumulator_s += step
            self._time_since_command_s += step
            if self._time_since_command_s > self.command_timeout_s:
                self.watchdog_active = True
                self._left_target = 0.0
                self._right_target = 0.0

            left_target = 0.0 if self.estopped else self._left_target
            right_target = 0.0 if self.estopped else self._right_target
            self._left_velocity = self._slew(self._left_velocity, left_target, step)
            self._right_velocity = self._slew(self._right_velocity, right_target, step)
            self._left_position += self._left_velocity * step
            self._right_position += self._right_velocity * step

            while self._telemetry_accumulator_s + 1e-12 >= self.telemetry_period_s:
                self._telemetry_accumulator_s -= self.telemetry_period_s
                self._emit_telemetry()

    def drain(self) -> bytes:
        """Return all queued controller output."""
        output = b''.join(self._queued)
        self._queued.clear()
        return output

    def boot(self) -> None:
        """Emit the same identity frame as a freshly reset controller."""
        self._left_target = 0.0
        self._right_target = 0.0
        self._time_since_command_s = math.inf
        self.watchdog_active = True
        self._queued.append(encode_frame('BOOT', 0, ('WILDEBEEST_BASE', 1)))

    @property
    def wheel_velocities(self):
        return self._left_velocity, self._right_velocity

    def _emit_telemetry(self) -> None:
        scale = self.ticks_per_revolution / (2.0 * math.pi)
        flags = 0
        if self.estopped:
            flags |= self.FLAG_SOFT_ESTOP
        if self.watchdog_active:
            flags |= self.FLAG_WATCHDOG
        self._queued.append(
            encode_frame(
                'ODOM',
                self._next_sequence(),
                (
                    self._int32(round(self._left_position * scale)),
                    self._int32(round(self._right_position * scale)),
                    round(self._left_velocity * 1000.0),
                    round(self._right_velocity * 1000.0),
                    round(self.battery_v * 1000.0),
                    flags,
                ),
            )
        )
        yaw_rate = (
            self.wheel_radius_m
            * (self._right_velocity - self._left_velocity)
            / self.wheel_separation_m
        )
        self._queued.append(
            encode_frame(
                'IMU',
                self._next_sequence(),
                (0, 0, 1000, 0, 0, round(math.degrees(yaw_rate) * 1000.0)),
            )
        )
        self._queued.append(
            encode_frame(
                'RANGE',
                self._next_sequence(),
                (round(self.front_range_m * 1000.0),),
            )
        )

    def _next_sequence(self) -> int:
        value = self._sequence
        self._sequence = (self._sequence + 1) & 0xFFFF
        return value

    def _slew(self, current: float, target: float, duration_s: float) -> float:
        limit = self.velocity_slew_rad_s2 * duration_s
        delta = max(-limit, min(limit, target - current))
        return current + delta

    @staticmethod
    def _require_fields(frame: Frame, expected: int) -> None:
        if len(frame.fields) != expected:
            raise ProtocolError(f'{frame.kind} expects {expected} fields')

    @staticmethod
    def _integer(text: str, minimum: int, maximum: int, name: str) -> int:
        try:
            value = int(text, 10)
        except ValueError as exc:
            raise ProtocolError(f'{name} is not an integer') from exc
        if str(value) != text or not minimum <= value <= maximum:
            raise ProtocolError(f'{name} is outside its accepted range')
        return value

    @staticmethod
    def _int32(value: int) -> int:
        return ((value + 2**31) % 2**32) - 2**31
