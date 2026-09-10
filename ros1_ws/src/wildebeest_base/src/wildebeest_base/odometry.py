"""Side-aggregate skid-steer encoder odometry without ROS dependencies."""

from dataclasses import dataclass
import math
from typing import Optional


class OdometryDiscontinuity(ValueError):
    """Raised before integrating an implausibly large encoder step."""


@dataclass(frozen=True)
class DriveGeometry:
    wheel_radius_m: float
    wheel_separation_m: float
    encoder_ticks_per_revolution: int

    def __post_init__(self) -> None:
        if self.wheel_radius_m <= 0.0:
            raise ValueError("wheel_radius_m must be positive")
        if self.wheel_separation_m <= 0.0:
            raise ValueError("wheel_separation_m must be positive")
        if self.encoder_ticks_per_revolution <= 0:
            raise ValueError("encoder_ticks_per_revolution must be positive")


@dataclass(frozen=True)
class OdometrySample:
    stamp_s: float
    x_m: float
    y_m: float
    yaw_rad: float
    linear_m_s: float
    angular_rad_s: float
    left_position_rad: float
    right_position_rad: float


def signed_int32_delta(current: int, previous: int) -> int:
    """Return a rollover-safe signed delta for int32 encoder counters."""

    return ((int(current) - int(previous) + 2**31) % 2**32) - 2**31


def normalize_angle(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


class DifferentialOdometry:
    def __init__(self, geometry: DriveGeometry, maximum_tick_delta: Optional[int] = None):
        self.geometry = geometry
        if maximum_tick_delta is not None and maximum_tick_delta <= 0:
            raise ValueError("maximum_tick_delta must be positive when provided")
        self.maximum_tick_delta = maximum_tick_delta
        self.reset()

    def reset(self) -> None:
        self.x_m = 0.0
        self.y_m = 0.0
        self.yaw_rad = 0.0
        self._last_left: Optional[int] = None
        self._last_right: Optional[int] = None
        self._last_stamp: Optional[float] = None

    def update(self, left_ticks: int, right_ticks: int, stamp_s: float) -> OdometrySample:
        radians_per_tick = 2.0 * math.pi / self.geometry.encoder_ticks_per_revolution
        left_position = int(left_ticks) * radians_per_tick
        right_position = int(right_ticks) * radians_per_tick

        if self._last_left is None:
            self._last_left = int(left_ticks)
            self._last_right = int(right_ticks)
            self._last_stamp = float(stamp_s)
            return OdometrySample(
                float(stamp_s), self.x_m, self.y_m, self.yaw_rad, 0.0, 0.0,
                left_position, right_position,
            )

        delta_left_ticks = signed_int32_delta(int(left_ticks), self._last_left)
        delta_right_ticks = signed_int32_delta(int(right_ticks), self._last_right)
        if self.maximum_tick_delta is not None and (
            abs(delta_left_ticks) > self.maximum_tick_delta
            or abs(delta_right_ticks) > self.maximum_tick_delta
        ):
            raise OdometryDiscontinuity(
                "encoder delta ({}, {}) exceeds {} ticks".format(
                    delta_left_ticks, delta_right_ticks, self.maximum_tick_delta
                )
            )
        delta_left = delta_left_ticks * radians_per_tick * self.geometry.wheel_radius_m
        delta_right = delta_right_ticks * radians_per_tick * self.geometry.wheel_radius_m
        distance = 0.5 * (delta_left + delta_right)
        delta_yaw = (delta_right - delta_left) / self.geometry.wheel_separation_m

        heading_midpoint = self.yaw_rad + 0.5 * delta_yaw
        self.x_m += distance * math.cos(heading_midpoint)
        self.y_m += distance * math.sin(heading_midpoint)
        self.yaw_rad = normalize_angle(self.yaw_rad + delta_yaw)

        dt = max(0.0, float(stamp_s) - float(self._last_stamp))
        linear = distance / dt if dt > 1.0e-6 else 0.0
        angular = delta_yaw / dt if dt > 1.0e-6 else 0.0

        self._last_left = int(left_ticks)
        self._last_right = int(right_ticks)
        self._last_stamp = float(stamp_s)
        return OdometrySample(
            float(stamp_s), self.x_m, self.y_m, self.yaw_rad, linear, angular,
            left_position, right_position,
        )
