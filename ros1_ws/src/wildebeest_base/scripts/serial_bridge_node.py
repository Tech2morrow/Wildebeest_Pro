#!/usr/bin/env python3
"""ROS 1 bridge for the Wildebeest Pro safety-oriented Arduino protocol."""

import math
import threading
import time
from typing import List, Optional

import rospy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import TransformStamped, Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import BatteryState, Imu, JointState, Range
from std_msgs.msg import Bool
from std_srvs.srv import Empty, EmptyResponse, SetBool, SetBoolResponse
import tf2_ros

from wildebeest_base.mock_transport import (
    FLAG_HARD_ESTOP,
    FLAG_IMU_FAULT,
    FLAG_LOW_BATTERY,
    FLAG_PROTOCOL_ERROR,
    FLAG_RANGE_TIMEOUT,
    FLAG_SOFT_ESTOP,
    FLAG_WATCHDOG,
    MockMcuTransport,
)
from wildebeest_base.odometry import DifferentialOdometry, DriveGeometry, OdometryDiscontinuity
from wildebeest_base.protocol import FrameStreamDecoder, ProtocolError, decode_frame, encode_frame
from wildebeest_base.safety import controller_boot_is_supported, motion_command_is_ready


def _quaternion_from_yaw(yaw: float):
    half = 0.5 * yaw
    return (0.0, 0.0, math.sin(half), math.cos(half))


def _covariance(diagonal):
    if len(diagonal) != 6:
        raise ValueError("covariance diagonal must have exactly six values")
    matrix = [0.0] * 36
    for index, value in enumerate(diagonal):
        matrix[index * 6 + index] = float(value)
    return matrix


class SerialTransport:
    """Small pyserial adapter with bounded input buffering."""

    def __init__(self, port: str, baud: int):
        self.port = port
        self.baud = int(baud)
        self.serial = None
        self.decoder = FrameStreamDecoder()

    @property
    def is_open(self) -> bool:
        return self.serial is not None and bool(self.serial.is_open)

    def open(self) -> None:
        import serial  # Kept optional for the mock and unit-test paths.

        self.serial = serial.Serial(
            port=self.port,
            baudrate=self.baud,
            timeout=0,
            write_timeout=0.2,
            exclusive=True,
        )
        # Preserve a pending BOOT line; dropping it can hide an MCU reset.
        self.decoder = FrameStreamDecoder()

    def close(self) -> None:
        if self.serial is not None:
            try:
                self.serial.close()
            finally:
                self.serial = None

    def write(self, payload: bytes) -> None:
        if not self.is_open:
            raise OSError("serial transport is closed")
        written = self.serial.write(payload)
        if written != len(payload):
            raise OSError("short serial write")

    def read_lines(self) -> List[bytes]:
        if not self.is_open:
            raise OSError("serial transport is closed")
        waiting = int(self.serial.in_waiting)
        if waiting <= 0:
            return []
        return self.decoder.feed(self.serial.read(min(waiting, 1024)))


class WildebeestBaseBridge:
    def __init__(self):
        wheel_radius = float(rospy.get_param("~wheel_radius_m", 0.033622))
        wheel_separation = float(rospy.get_param("~wheel_separation_m", 0.121843))
        ticks_per_revolution = int(rospy.get_param("~encoder_ticks_per_revolution", 600))
        self.geometry = DriveGeometry(wheel_radius, wheel_separation, ticks_per_revolution)
        self.odometry = DifferentialOdometry(
            self.geometry,
            maximum_tick_delta=int(rospy.get_param("~max_encoder_tick_delta", 1200)),
        )

        self.odom_frame = rospy.get_param("~odom_frame", "odom")
        self.base_frame = rospy.get_param("~base_frame", "base_link")
        self.imu_frame = rospy.get_param("~imu_frame", "imu_link")
        self.range_frame = rospy.get_param("~range_frame", "ultrasonic_front_link")
        left_wheel_joint_names = rospy.get_param(
            "~left_wheel_joint_names",
            ["front_left_wheel_joint", "rear_left_wheel_joint"],
        )
        right_wheel_joint_names = rospy.get_param(
            "~right_wheel_joint_names",
            ["front_right_wheel_joint", "rear_right_wheel_joint"],
        )
        if (
            not isinstance(left_wheel_joint_names, (list, tuple))
            or not isinstance(right_wheel_joint_names, (list, tuple))
            or not left_wheel_joint_names
            or not right_wheel_joint_names
            or not all(isinstance(name, str) and name for name in left_wheel_joint_names)
            or not all(isinstance(name, str) and name for name in right_wheel_joint_names)
        ):
            raise rospy.ROSInitException("wheel joint name lists must contain non-empty strings")
        self.left_wheel_joint_names = list(left_wheel_joint_names)
        self.right_wheel_joint_names = list(right_wheel_joint_names)
        self.publish_odom_tf = bool(rospy.get_param("~publish_odom_tf", False))
        self.max_linear = float(rospy.get_param("~max_linear_m_s", 0.45))
        self.max_angular = float(rospy.get_param("~max_angular_rad_s", 1.80))
        self.command_timeout = float(rospy.get_param("~cmd_vel_timeout_s", 0.25))
        self.reconnect_delay = float(rospy.get_param("~reconnect_delay_s", 2.0))
        command_rate = float(rospy.get_param("~command_rate_hz", 20.0))
        if not 0.0 < self.max_linear <= 0.45:
            raise rospy.ROSInitException("~max_linear_m_s must be in (0, 0.45]")
        if not 0.0 < self.max_angular <= 1.80:
            raise rospy.ROSInitException("~max_angular_rad_s must be in (0, 1.80]")
        if command_rate <= 0.0 or self.command_timeout <= 0.0 or self.reconnect_delay <= 0.0:
            raise rospy.ROSInitException("rates and timeouts must be positive")
        self.pose_covariance = _covariance(
            rospy.get_param("~pose_covariance_diagonal", [0.05, 0.05, 99999, 99999, 99999, 0.10])
        )
        self.twist_covariance = _covariance(
            rospy.get_param("~twist_covariance_diagonal", [0.08, 0.08, 99999, 99999, 99999, 0.15])
        )

        transport_name = str(rospy.get_param("~transport", "serial")).lower()
        if transport_name == "mock":
            self.transport = MockMcuTransport(
                self.geometry,
                watchdog_s=float(rospy.get_param("~mcu_watchdog_s", 0.30)),
            )
        elif transport_name == "serial":
            self.transport = SerialTransport(
                str(rospy.get_param("~port", "/dev/wildebeest-base")),
                int(rospy.get_param("~baud", 115200)),
            )
        else:
            raise rospy.ROSInitException("~transport must be 'serial' or 'mock'")
        self.transport_name = transport_name
        self.require_estop_clear_after_boot = bool(
            rospy.get_param("~require_estop_clear_after_boot", True)
        )
        if not self.require_estop_clear_after_boot:
            raise rospy.ROSInitException(
                "~require_estop_clear_after_boot=false is unsafe and unsupported"
            )

        self.odom_pub = rospy.Publisher("/wheel/odometry", Odometry, queue_size=10)
        self.joint_pub = rospy.Publisher("/joint_states", JointState, queue_size=10)
        self.imu_pub = rospy.Publisher("/imu/data_raw", Imu, queue_size=20)
        self.range_pub = rospy.Publisher("/range/front", Range, queue_size=10)
        self.battery_pub = rospy.Publisher("/battery_state", BatteryState, queue_size=2)
        self.diagnostic_pub = rospy.Publisher("/diagnostics", DiagnosticArray, queue_size=2)
        self.tf_broadcaster = tf2_ros.TransformBroadcaster() if self.publish_odom_tf else None

        self.lock = threading.RLock()
        self.latest_command = Twist()
        self.latest_command_time = time.monotonic() - self.command_timeout
        self.local_estop = False
        self.controller_stop_latched = False
        self.estop_clear_pending = False
        self.controller_ready = False
        self.sequence = 0
        self.next_reconnect = 0.0
        self.last_rx_monotonic: Optional[float] = None
        self.last_odom_monotonic: Optional[float] = None
        self.last_imu_monotonic: Optional[float] = None
        self.last_range_monotonic: Optional[float] = None
        self.last_pong_monotonic: Optional[float] = None
        self.last_ping_monotonic = 0.0
        self.last_diagnostic_monotonic = 0.0
        self.bad_frames = 0
        self.io_errors = 0
        self.received_frames = 0
        self.mcu_flags = FLAG_WATCHDOG
        self.battery_voltage = float("nan")
        self.motion_ready_after: Optional[float] = None
        self.last_telemetry_sequence: Optional[int] = None
        self.telemetry_sequence_gaps = 0
        self.controller_boots = 0
        self.controller_errors = 0
        self.odometry_discontinuities = 0
        self.firmware_identity = "unknown"
        self.firmware_version = "unknown"

        self.command_sub = rospy.Subscriber("/cmd_vel", Twist, self._command_callback, queue_size=1)
        self.estop_sub = rospy.Subscriber(
            "/wildebeest/estop", Bool, self._estop_callback, queue_size=1
        )
        self.estop_service = rospy.Service("/base/set_estop", SetBool, self._set_estop)
        self.reset_odometry_service = rospy.Service(
            "/base/reset_odometry", Empty, self._reset_odometry
        )
        self.timer = rospy.Timer(rospy.Duration(1.0 / command_rate), self._cycle)
        rospy.on_shutdown(self.shutdown)
        rospy.loginfo("Wildebeest base bridge using %s transport", transport_name)

    def _next_sequence(self) -> int:
        sequence = self.sequence
        self.sequence = (self.sequence + 1) & 0xFFFF
        return sequence

    def _command_callback(self, message: Twist) -> None:
        with self.lock:
            if not math.isfinite(message.linear.x) or not math.isfinite(message.angular.z):
                self._invalidate_motion(time.monotonic())
                rospy.logerr_throttle(2.0, "Rejected non-finite cmd_vel")
                return
            self.latest_command = message
            self.latest_command_time = time.monotonic()

    def _invalidate_motion(self, now: float) -> None:
        """Drop the cached command and require one strictly newer than ``now``."""
        self.latest_command = Twist()
        self.latest_command_time = float(now) - self.command_timeout
        self.motion_ready_after = float(now)

    def _invalidate_controller(self, now: Optional[float] = None) -> None:
        """Fail closed until a new, exact BOOT handshake is validated."""
        instant = time.monotonic() if now is None else float(now)
        self.controller_ready = False
        self.local_estop = True
        self.controller_stop_latched = True
        self.estop_clear_pending = False
        self.latest_command = Twist()
        self.latest_command_time = instant - self.command_timeout
        self.motion_ready_after = None

    def _reset_odometry(self, _request) -> EmptyResponse:
        with self.lock:
            self.odometry.reset()
        rospy.loginfo("Encoder odometry origin reset; the next ODOM frame establishes its baseline")
        return EmptyResponse()

    def _set_estop(self, request) -> SetBoolResponse:
        # A service call is an explicit transition request, even if the last
        # locally observed state is the same (the MCU may have latched a stop).
        return self._apply_estop(bool(request.data), force=True)

    def _estop_callback(self, message: Bool) -> None:
        response = self._apply_estop(bool(message.data), force=False)
        if not response.success:
            rospy.logerr_throttle(2.0, response.message)

    def _apply_estop(self, engaged: bool, force: bool = False) -> SetBoolResponse:
        with self.lock:
            engaged = bool(engaged)
            if not engaged and self.estop_clear_pending and not force:
                return SetBoolResponse(True, "software ESTOP clear is awaiting clean ODOM flags")
            transition = force or self.local_estop != engaged or self.controller_stop_latched
            if not transition:
                return SetBoolResponse(True, "software ESTOP state unchanged")
            now = time.monotonic()
            self._invalidate_motion(now)
            if not self.controller_ready:
                self.local_estop = True
                self.controller_stop_latched = True
                return SetBoolResponse(False, "ESTOP not sent; controller BOOT is not validated")
            if engaged:
                # Fail closed before attempting I/O.
                self.local_estop = True
                self.controller_stop_latched = True
                self.estop_clear_pending = False
            try:
                if not self.transport.is_open:
                    if not engaged:
                        self.local_estop = True
                        self.controller_stop_latched = True
                        self.estop_clear_pending = False
                    return SetBoolResponse(
                        False, "ESTOP clear not confirmed; controller is disconnected"
                    )
                self.transport.write(
                    encode_frame("ESTOP", self._next_sequence(), int(engaged))
                )
            except Exception as exc:  # SerialException is optional.
                self.local_estop = True
                self.controller_stop_latched = True
                self.estop_clear_pending = False
                self._disconnect("could not transmit ESTOP: {}".format(exc))
                return SetBoolResponse(False, "ESTOP state not confirmed; MCU watchdog will stop motion")
            self.local_estop = engaged
            if engaged:
                self.controller_stop_latched = True
            else:
                # ESTOP has no ACK frame. Keep the host gate latched until an
                # ODOM frame proves that both hard and software-stop bits cleared.
                self.controller_stop_latched = True
                self.estop_clear_pending = True
        if engaged:
            return SetBoolResponse(True, "software ESTOP engaged (verify ODOM flags)")
        return SetBoolResponse(True, "software ESTOP clear sent; awaiting clean ODOM flags")

    def _disconnect(self, reason: str) -> None:
        if self.transport.is_open:
            rospy.logwarn("Closing base transport: %s", reason)
        try:
            self.transport.close()
        except Exception:
            pass
        self._invalidate_controller()
        self.io_errors += 1
        self.next_reconnect = time.monotonic() + self.reconnect_delay

    def _ensure_connected(self, now: float) -> bool:
        if self.transport.is_open:
            return True
        if now < self.next_reconnect:
            return False
        try:
            self.transport.open()
            self.odometry.reset()
            self.last_telemetry_sequence = None
            self._invalidate_controller(now)
            rospy.loginfo("Base transport connected")
            return True
        except Exception as exc:
            rospy.logwarn_throttle(10.0, "Base transport unavailable: %s", exc)
            self.next_reconnect = now + self.reconnect_delay
            return False

    def _cycle(self, _event) -> None:
        with self.lock:
            now = time.monotonic()
            if not self._ensure_connected(now):
                self._publish_diagnostics(now)
                return
            if not self.controller_ready:
                try:
                    handshake_lines = self.transport.read_lines()
                    for line in handshake_lines:
                        self._handle_line(line)
                except ProtocolError as exc:
                    self.bad_frames += 1
                    rospy.logerr("Controller handshake rejected: %s", exc)
                    self._disconnect("controller handshake rejected")
                except Exception as exc:
                    self._disconnect(str(exc))
                self._publish_diagnostics(now)
                return
            ready_for_motion = motion_command_is_ready(
                now,
                self.latest_command_time,
                self.motion_ready_after,
                self.command_timeout,
                self.controller_ready,
            )
            stopped = (
                self.local_estop
                or self.controller_stop_latched
                or bool(self.mcu_flags & (FLAG_HARD_ESTOP | FLAG_SOFT_ESTOP))
            )
            linear = 0.0 if not ready_for_motion or stopped else self.latest_command.linear.x
            angular = 0.0 if not ready_for_motion or stopped else self.latest_command.angular.z
            linear = max(-self.max_linear, min(self.max_linear, float(linear)))
            angular = max(-self.max_angular, min(self.max_angular, float(angular)))
            try:
                command = encode_frame(
                    "CMD",
                    self._next_sequence(),
                    int(round(linear * 1000.0)),
                    int(round(angular * 1000.0)),
                )
                self.transport.write(command)
                if now - self.last_ping_monotonic >= 1.0:
                    self.transport.write(encode_frame("PING", self._next_sequence()))
                    self.last_ping_monotonic = now
                lines = self.transport.read_lines()
            except ProtocolError as exc:
                self.bad_frames += 1
                rospy.logerr_throttle(5.0, "Internal command encoding rejected: %s", exc)
                self._disconnect("internal protocol encoding failure")
                lines = []
            except Exception as exc:
                self._disconnect(str(exc))
                lines = []
            for line in lines:
                try:
                    self._handle_line(line)
                except ProtocolError as exc:
                    self.bad_frames += 1
                    rospy.logwarn_throttle(5.0, "Rejected base frame: %s", exc)
                    self._disconnect("controller protocol frame rejected")
                    break
                except Exception as exc:
                    self._disconnect(str(exc))
                    break
            self._publish_diagnostics(now)

    def _handle_line(self, line: bytes) -> None:
        try:
            frame = decode_frame(line)
        except ProtocolError:
            self.bad_frames += 1
            raise
        self.received_frames += 1
        self.last_rx_monotonic = time.monotonic()
        if frame.kind != "BOOT" and not self.controller_ready:
            raise ProtocolError("{} received before validated BOOT".format(frame.kind))
        if frame.kind == "ODOM":
            self._record_telemetry_sequence(frame.sequence)
            self.last_odom_monotonic = self.last_rx_monotonic
            self._publish_odom(frame)
        elif frame.kind == "IMU":
            self._record_telemetry_sequence(frame.sequence)
            self.last_imu_monotonic = self.last_rx_monotonic
            self._publish_imu(frame)
        elif frame.kind == "RANGE":
            self._record_telemetry_sequence(frame.sequence)
            self.last_range_monotonic = self.last_rx_monotonic
            self._publish_range(frame)
        elif frame.kind == "PONG":
            self.last_pong_monotonic = self.last_rx_monotonic
        elif frame.kind == "BOOT":
            identity, version = frame.fields
            if not controller_boot_is_supported(frame.sequence, identity, version):
                self._invalidate_controller(self.last_rx_monotonic)
                raise ProtocolError(
                    "unsupported controller BOOT {},{}/{}".format(
                        frame.sequence, identity, version
                    )
                )
            self.firmware_identity, self.firmware_version = identity, version
            self.controller_boots += 1
            self.odometry.reset()
            self.last_telemetry_sequence = None
            self._invalidate_motion(self.last_rx_monotonic)
            self.local_estop = True
            self.controller_stop_latched = True
            self.estop_clear_pending = False
            self.controller_ready = True
            self.transport.write(encode_frame("ESTOP", self._next_sequence(), 1))
            rospy.logwarn("Controller reboot detected; software ESTOP engaged until explicitly cleared")
            rospy.loginfo("Base controller booted: %s protocol v%s", frame.fields[0], frame.fields[1])
        elif frame.kind == "ERR":
            self.bad_frames += 1
            self.controller_errors += 1
            raise ProtocolError("base controller rejected command: {}".format(frame.fields[0]))
        else:
            self.bad_frames += 1

    def _record_telemetry_sequence(self, sequence: int) -> None:
        if self.last_telemetry_sequence is not None:
            expected = (self.last_telemetry_sequence + 1) & 0xFFFF
            if sequence != expected:
                self.telemetry_sequence_gaps += (sequence - expected) & 0xFFFF
        self.last_telemetry_sequence = sequence

    def _publish_odom(self, frame) -> None:
        left_ticks, right_ticks, left_mrad_s, right_mrad_s, battery_mv, flags = (
            int(value) for value in frame.fields
        )
        stop_flags = flags & (FLAG_HARD_ESTOP | FLAG_SOFT_ESTOP)
        if flags & FLAG_PROTOCOL_ERROR:
            raise ProtocolError("controller reported its protocol-error flag")
        if stop_flags:
            if not self.controller_stop_latched or self.estop_clear_pending:
                self.local_estop = True
                self.controller_stop_latched = True
                self.estop_clear_pending = False
                self._invalidate_motion(time.monotonic())
                rospy.logerr("Controller stop flag latched on host; explicit ESTOP clear required")
        elif self.estop_clear_pending:
            self.local_estop = False
            self.controller_stop_latched = False
            self.estop_clear_pending = False
            self._invalidate_motion(time.monotonic())
            rospy.loginfo("Controller confirmed ESTOP clear; waiting for a fresh cmd_vel")
        stamp = rospy.Time.now()
        try:
            sample = self.odometry.update(left_ticks, right_ticks, stamp.to_sec())
        except OdometryDiscontinuity as exc:
            self.odometry_discontinuities += 1
            rospy.logerr("Discarded encoder discontinuity: %s", exc)
            self.odometry.reset()
            sample = self.odometry.update(left_ticks, right_ticks, stamp.to_sec())
        left_rad_s = left_mrad_s / 1000.0
        right_rad_s = right_mrad_s / 1000.0
        linear = 0.5 * (left_rad_s + right_rad_s) * self.geometry.wheel_radius_m
        angular = (
            (right_rad_s - left_rad_s)
            * self.geometry.wheel_radius_m
            / self.geometry.wheel_separation_m
        )
        qx, qy, qz, qw = _quaternion_from_yaw(sample.yaw_rad)

        message = Odometry()
        message.header.stamp = stamp
        message.header.frame_id = self.odom_frame
        message.child_frame_id = self.base_frame
        message.pose.pose.position.x = sample.x_m
        message.pose.pose.position.y = sample.y_m
        message.pose.pose.orientation.x = qx
        message.pose.pose.orientation.y = qy
        message.pose.pose.orientation.z = qz
        message.pose.pose.orientation.w = qw
        message.pose.covariance = self.pose_covariance
        message.twist.twist.linear.x = linear
        message.twist.twist.angular.z = angular
        message.twist.covariance = self.twist_covariance
        self.odom_pub.publish(message)

        joints = JointState()
        joints.header.stamp = stamp
        joints.name = self.left_wheel_joint_names + self.right_wheel_joint_names
        joints.position = (
            [sample.left_position_rad] * len(self.left_wheel_joint_names)
            + [sample.right_position_rad] * len(self.right_wheel_joint_names)
        )
        joints.velocity = (
            [left_rad_s] * len(self.left_wheel_joint_names)
            + [right_rad_s] * len(self.right_wheel_joint_names)
        )
        self.joint_pub.publish(joints)

        if self.tf_broadcaster is not None:
            transform = TransformStamped()
            transform.header = message.header
            transform.child_frame_id = self.base_frame
            transform.transform.translation.x = sample.x_m
            transform.transform.translation.y = sample.y_m
            transform.transform.rotation = message.pose.pose.orientation
            self.tf_broadcaster.sendTransform(transform)

        self.mcu_flags = flags
        self.battery_voltage = battery_mv / 1000.0
        battery = BatteryState()
        battery.header.stamp = stamp
        battery.voltage = self.battery_voltage
        battery.present = battery_mv > 0
        battery.percentage = float("nan")
        battery.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
        battery.power_supply_health = (
            BatteryState.POWER_SUPPLY_HEALTH_UNSPEC_FAILURE
            if flags & FLAG_LOW_BATTERY
            else BatteryState.POWER_SUPPLY_HEALTH_GOOD
        )
        battery.power_supply_technology = BatteryState.POWER_SUPPLY_TECHNOLOGY_LION
        self.battery_pub.publish(battery)

    def _publish_imu(self, frame) -> None:
        ax, ay, az, gx, gy, gz = (int(value) for value in frame.fields)
        message = Imu()
        message.header.stamp = rospy.Time.now()
        message.header.frame_id = self.imu_frame
        message.orientation_covariance[0] = -1.0
        millidegrees_to_radians = math.pi / 180000.0
        message.angular_velocity.x = gx * millidegrees_to_radians
        message.angular_velocity.y = gy * millidegrees_to_radians
        message.angular_velocity.z = gz * millidegrees_to_radians
        message.linear_acceleration.x = ax * 9.80665 / 1000.0
        message.linear_acceleration.y = ay * 9.80665 / 1000.0
        message.linear_acceleration.z = az * 9.80665 / 1000.0
        message.angular_velocity_covariance = [0.0004, 0.0, 0.0, 0.0, 0.0004, 0.0, 0.0, 0.0, 0.0009]
        message.linear_acceleration_covariance = [0.01, 0.0, 0.0, 0.0, 0.01, 0.0, 0.0, 0.0, 0.02]
        self.imu_pub.publish(message)

    def _publish_range(self, frame) -> None:
        range_mm = int(frame.fields[0])
        message = Range()
        message.header.stamp = rospy.Time.now()
        message.header.frame_id = self.range_frame
        message.radiation_type = Range.ULTRASOUND
        message.field_of_view = float(rospy.get_param("~front_range_field_of_view_rad", 0.26))
        message.min_range = float(rospy.get_param("~front_range_min_m", 0.02))
        message.max_range = float(rospy.get_param("~front_range_max_m", 2.0))
        measured_range = range_mm / 1000.0
        if measured_range < message.min_range:
            # sensor_msgs/Range uses -Inf for an obstacle closer than min range.
            message.range = float("-inf")
        elif measured_range > message.max_range:
            message.range = float("inf")
        else:
            message.range = measured_range
        self.range_pub.publish(message)

    def _publish_diagnostics(self, now: float) -> None:
        if now - self.last_diagnostic_monotonic < 1.0:
            return
        self.last_diagnostic_monotonic = now
        connected = bool(self.transport.is_open)
        rx_age = float("inf") if self.last_rx_monotonic is None else now - self.last_rx_monotonic
        odom_age = float("inf") if self.last_odom_monotonic is None else now - self.last_odom_monotonic
        flags = self.mcu_flags
        level = DiagnosticStatus.OK
        summary = "base link healthy"
        if not connected or odom_age > 1.0:
            level = DiagnosticStatus.ERROR
            summary = "base telemetry unavailable"
        elif flags & (FLAG_HARD_ESTOP | FLAG_SOFT_ESTOP):
            level = DiagnosticStatus.ERROR
            summary = "base emergency stop active"
        elif flags & (
            FLAG_WATCHDOG
            | FLAG_PROTOCOL_ERROR
            | FLAG_LOW_BATTERY
            | FLAG_IMU_FAULT
            | FLAG_RANGE_TIMEOUT
        ):
            level = DiagnosticStatus.WARN
            summary = "base safety flag active"
        elif flags & ~0x007F:
            level = DiagnosticStatus.WARN
            summary = "unknown controller status flag active"
        status = DiagnosticStatus(
            level=level,
            name="Wildebeest Pro/base serial bridge",
            hardware_id="arduino-uno",
            message=summary,
            values=[
                KeyValue("transport", self.transport_name),
                KeyValue("connected", str(connected).lower()),
                KeyValue("controller_ready", str(self.controller_ready).lower()),
                KeyValue("rx_age_s", "{:.3f}".format(rx_age)),
                KeyValue("odom_age_s", "{:.3f}".format(odom_age)),
                KeyValue("battery_v", "{:.3f}".format(self.battery_voltage)),
                KeyValue("mcu_flags", "0x{:04X}".format(flags)),
                KeyValue("hard_estop", str(bool(flags & FLAG_HARD_ESTOP)).lower()),
                KeyValue("soft_estop", str(bool(flags & FLAG_SOFT_ESTOP)).lower()),
                KeyValue("host_stop_latched", str(self.controller_stop_latched).lower()),
                KeyValue("estop_clear_pending", str(self.estop_clear_pending).lower()),
                KeyValue("watchdog", str(bool(flags & FLAG_WATCHDOG)).lower()),
                KeyValue("protocol_error", str(bool(flags & FLAG_PROTOCOL_ERROR)).lower()),
                KeyValue("range_timeout", str(bool(flags & FLAG_RANGE_TIMEOUT)).lower()),
                KeyValue("received_frames", str(self.received_frames)),
                KeyValue("bad_frames", str(self.bad_frames)),
                KeyValue("io_errors", str(self.io_errors)),
                KeyValue("telemetry_sequence_gaps", str(self.telemetry_sequence_gaps)),
                KeyValue("controller_boots", str(self.controller_boots)),
                KeyValue("controller_errors", str(self.controller_errors)),
                KeyValue("odometry_discontinuities", str(self.odometry_discontinuities)),
                KeyValue("firmware_identity", self.firmware_identity),
                KeyValue("firmware_protocol_version", self.firmware_version),
            ],
        )
        array = DiagnosticArray()
        array.header.stamp = rospy.Time.now()
        array.status = [status]
        self.diagnostic_pub.publish(array)

    def shutdown(self) -> None:
        with self.lock:
            try:
                if self.transport.is_open:
                    self.transport.write(encode_frame("CMD", self._next_sequence(), 0, 0))
                    self.transport.write(encode_frame("ESTOP", self._next_sequence(), 1))
            except Exception:
                pass
            try:
                self.transport.close()
            except Exception:
                pass


def main() -> None:
    rospy.init_node("base_serial_bridge")
    WildebeestBaseBridge()
    rospy.spin()


if __name__ == "__main__":
    main()
