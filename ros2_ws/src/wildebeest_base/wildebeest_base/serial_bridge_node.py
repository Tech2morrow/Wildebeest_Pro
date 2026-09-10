"""ROS 2 node joining the Arduino protocol to standard mobile-robot topics."""

import math
import time
from typing import Optional

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import TransformStamped, Twist
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import BatteryState, Imu, JointState, Range
from std_msgs.msg import Bool
from std_srvs.srv import Empty, SetBool
from tf2_ros import TransformBroadcaster

from .mock_controller import MockController
from .protocol import (
    encode_cmd,
    encode_estop,
    encode_ping,
    Frame,
    FrameStreamDecoder,
    ImuTelemetry,
    OdomTelemetry,
    parse_telemetry,
    ProtocolError,
    RangeTelemetry,
    validate_controller_boot,
)
from .transport import MockTransport, PySerialTransport, Transport, TransportError


class SerialBridge(Node):
    """Fail-closed bridge for the Wildebeest low-level controller."""

    def __init__(self) -> None:
        super().__init__('base_controller')
        self._declare_parameters()
        self._load_parameters()

        if self._transport_mode == 'serial':
            self._transport: Transport = PySerialTransport(self._port, self._baudrate)
        else:
            controller = MockController(
                wheel_radius_m=self._wheel_radius,
                wheel_separation_m=self._wheel_separation,
                ticks_per_revolution=self._ticks_per_revolution,
                command_timeout_s=self._command_timeout,
                max_wheel_rad_s=self._max_wheel_speed,
            )
            self._transport = MockTransport(controller)

        self._decoder = FrameStreamDecoder()
        self._tf_broadcaster = TransformBroadcaster(self) if self._publish_tf else None
        self._odom_pub = self.create_publisher(Odometry, '/wheel/odometry', 20)
        self._joint_pub = self.create_publisher(JointState, '/joint_states', 20)
        self._imu_pub = self.create_publisher(Imu, '/imu/data_raw', qos_profile_sensor_data)
        self._range_pub = self.create_publisher(
            Range, '/range/front', qos_profile_sensor_data
        )
        self._battery_pub = self.create_publisher(BatteryState, '/battery_state', 10)
        self._diagnostic_pub = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self._cmd_sub = self.create_subscription(Twist, '/cmd_vel', self._on_cmd_vel, 10)
        self._estop_sub = self.create_subscription(
            Bool, '/wildebeest/estop', self._on_estop_topic, 10
        )
        self._estop_service = self.create_service(
            SetBool, '/base/set_estop', self._on_emergency_stop
        )
        self._reset_service = self.create_service(
            Empty, '/base/reset_odometry', self._on_reset_odometry
        )

        self._x = 0.0
        self._y = 0.0
        self._yaw = 0.0
        self._left_joint_position = 0.0
        self._right_joint_position = 0.0
        self._previous_left_ticks: Optional[int] = None
        self._previous_right_ticks: Optional[int] = None
        self._last_odom_s: Optional[float] = None
        self._last_imu_s: Optional[float] = None
        self._last_range_s: Optional[float] = None
        self._last_pong_s: Optional[float] = None
        self._last_command_s: Optional[float] = None
        self._last_ping_s = -math.inf
        self._last_connection_attempt_s = -math.inf
        self._command_timed_out = True
        self._firmware_flags = MockController.FLAG_WATCHDOG
        self._firmware_stopped = False
        self._host_estop_latched = True
        self._estopped = True
        self._controller_ready = False
        self._battery_v = math.nan
        self._sequence = 0
        self._last_telemetry_sequence: Optional[int] = None
        self._valid_frames = 0
        self._rejected_frames = 0
        self._sequence_gaps = 0
        self._transport_errors = 0
        self._unknown_frames = 0
        self._controller_errors = 0
        self._last_controller_error = ''
        self._firmware_identity = 'unknown'
        self._firmware_version = 'unknown'
        self._last_protocol_warning_s = -math.inf

        self._poll_timer = self.create_timer(1.0 / self._read_rate, self._poll)
        self._diagnostic_timer = self.create_timer(1.0, self._publish_diagnostics)
        self.get_logger().info(
            f'base bridge configured for {self._transport_mode} transport'
            + (f' on {self._port}' if self._transport_mode == 'serial' else '')
        )

    def _declare_parameters(self) -> None:
        defaults = {
            'transport': 'serial',
            'port': '/dev/wildebeest-base',
            'baudrate': 115200,
            'reconnect_interval_s': 2.0,
            'read_rate_hz': 100.0,
            'telemetry_timeout_s': 1.0,
            'command_timeout_s': 0.3,
            'ping_interval_s': 1.0,
            'max_linear_m_s': 0.45,
            'max_angular_rad_s': 1.8,
            'max_wheel_rad_s': 18.0,
            'wheel_radius_m': 0.033622,
            'wheel_separation_m': 0.121843,
            'ticks_per_revolution': 600,
            'publish_odom_tf': True,
            'odom_frame': 'odom',
            'base_frame': 'base_link',
            'imu_frame': 'imu_link',
            'range_frame': 'ultrasonic_front_link',
            'left_wheel_joints': [
                'left_front_wheel_joint',
                'left_rear_wheel_joint',
            ],
            'right_wheel_joints': [
                'right_front_wheel_joint',
                'right_rear_wheel_joint',
            ],
            'range_min_m': 0.02,
            'range_max_m': 2.0,
            'range_field_of_view_rad': 0.26,
            'estop_on_shutdown': True,
            'release_estop_on_connect': False,
        }
        for name, value in defaults.items():
            self.declare_parameter(name, value)

    def _load_parameters(self) -> None:
        def value(name):
            return self.get_parameter(name).value

        self._transport_mode = str(value('transport')).lower()
        self._port = str(value('port'))
        self._baudrate = int(value('baudrate'))
        self._reconnect_interval = float(value('reconnect_interval_s'))
        self._read_rate = float(value('read_rate_hz'))
        self._telemetry_timeout = float(value('telemetry_timeout_s'))
        self._command_timeout = float(value('command_timeout_s'))
        self._ping_interval = float(value('ping_interval_s'))
        self._max_linear = float(value('max_linear_m_s'))
        self._max_angular = float(value('max_angular_rad_s'))
        self._max_wheel_speed = float(value('max_wheel_rad_s'))
        self._wheel_radius = float(value('wheel_radius_m'))
        self._wheel_separation = float(value('wheel_separation_m'))
        self._ticks_per_revolution = int(value('ticks_per_revolution'))
        self._publish_tf = bool(value('publish_odom_tf'))
        self._odom_frame = str(value('odom_frame'))
        self._base_frame = str(value('base_frame'))
        self._imu_frame = str(value('imu_frame'))
        self._range_frame = str(value('range_frame'))
        self._left_joints = [str(name) for name in value('left_wheel_joints')]
        self._right_joints = [str(name) for name in value('right_wheel_joints')]
        self._range_min = float(value('range_min_m'))
        self._range_max = float(value('range_max_m'))
        self._range_fov = float(value('range_field_of_view_rad'))
        self._estop_on_shutdown = bool(value('estop_on_shutdown'))
        self._release_estop_on_connect = bool(value('release_estop_on_connect'))

        positive = {
            'baudrate': self._baudrate,
            'reconnect_interval_s': self._reconnect_interval,
            'read_rate_hz': self._read_rate,
            'telemetry_timeout_s': self._telemetry_timeout,
            'command_timeout_s': self._command_timeout,
            'ping_interval_s': self._ping_interval,
            'max_linear_m_s': self._max_linear,
            'max_angular_rad_s': self._max_angular,
            'max_wheel_rad_s': self._max_wheel_speed,
            'wheel_radius_m': self._wheel_radius,
            'wheel_separation_m': self._wheel_separation,
            'ticks_per_revolution': self._ticks_per_revolution,
            'range_max_m': self._range_max,
            'range_field_of_view_rad': self._range_fov,
        }
        invalid = [name for name, number in positive.items() if number <= 0]
        if invalid:
            raise ValueError('parameters must be positive: ' + ', '.join(invalid))
        if self._transport_mode not in ('serial', 'mock'):
            raise ValueError("transport must be either 'serial' or 'mock'")
        if self._max_linear > 0.45 or self._max_angular > 1.8:
            raise ValueError('configured speed exceeds protocol safety bounds')
        if not 0.0 < self._range_min < self._range_max <= 2.0:
            raise ValueError('range limits must satisfy 0 < min < max <= 2 metres')
        if len(self._left_joints) != 2 or len(self._right_joints) != 2:
            raise ValueError('four-wheel skid steer requires two joint names per side')

    def _poll(self) -> None:
        now = time.monotonic()
        if not self._transport.is_open:
            self._connect(now)
            return

        if now - self._last_ping_s >= self._ping_interval:
            self._send(encode_ping(self._next_sequence()))
            self._last_ping_s = now

        if (
            self._last_command_s is not None
            and not self._command_timed_out
            and now - self._last_command_s > self._command_timeout
        ):
            self._send_velocity(0.0, 0.0)
            self._command_timed_out = True
            self.get_logger().warning('cmd_vel timeout; commanded a controlled stop')

        try:
            incoming = self._transport.read()
        except TransportError as exc:
            self._handle_transport_error(exc)
            return
        if not incoming:
            return
        frames, errors = self._decoder.feed(incoming)
        self._rejected_frames += len(errors)
        if errors and now - self._last_protocol_warning_s > 5.0:
            self.get_logger().warning(f'rejected serial frame: {errors[-1]}')
            self._last_protocol_warning_s = now
        for frame in frames:
            try:
                self._handle_frame(frame, now)
                self._valid_frames += 1
            except ProtocolError as exc:
                self._rejected_frames += 1
                if now - self._last_protocol_warning_s > 5.0:
                    self.get_logger().warning(f'rejected telemetry: {exc}')
                    self._last_protocol_warning_s = now
            if not self._transport.is_open:
                break

    def _connect(self, now: float) -> None:
        if now - self._last_connection_attempt_s < self._reconnect_interval:
            return
        self._last_connection_attempt_s = now
        self._controller_ready = False
        self._host_estop_latched = True
        self._firmware_stopped = False
        self._estopped = True
        self._last_command_s = None
        self._command_timed_out = True
        try:
            self._transport.open()
            self._decoder.clear()
            self._previous_left_ticks = None
            self._previous_right_ticks = None
            self._last_telemetry_sequence = None
            if not self._send_velocity(0.0, 0.0):
                return
            if not self._send(encode_ping(self._next_sequence())):
                return
            self._last_ping_s = now
            self.get_logger().info('controller transport connected')
        except TransportError as exc:
            self._handle_transport_error(exc, close=False)

    def _handle_frame(self, frame: Frame, now: float) -> None:
        telemetry = parse_telemetry(frame)
        if isinstance(telemetry, OdomTelemetry):
            self._record_telemetry_sequence(telemetry.sequence)
            self._last_odom_s = now
            self._battery_v = telemetry.battery_v
            self._firmware_flags = telemetry.flags
            if telemetry.flags & MockController.FLAG_PROTOCOL_ERROR:
                self._controller_errors += 1
                self._last_controller_error = 'FIRMWARE_PROTOCOL_ERROR'
                self._invalidate_controller(
                    'controller reported its protocol-error flag'
                )
                return
            stop_flags = MockController.FLAG_HARD_ESTOP | MockController.FLAG_SOFT_ESTOP
            self._firmware_stopped = bool(telemetry.flags & stop_flags)
            stopped = self._host_estop_latched or self._firmware_stopped
            if stopped and not self._estopped:
                self._last_command_s = None
                self._command_timed_out = True
            self._estopped = stopped
            self._publish_odometry(telemetry)
        elif isinstance(telemetry, ImuTelemetry):
            self._record_telemetry_sequence(telemetry.sequence)
            self._last_imu_s = now
            self._publish_imu(telemetry)
        elif isinstance(telemetry, RangeTelemetry):
            self._record_telemetry_sequence(telemetry.sequence)
            self._last_range_s = now
            self._publish_range(telemetry)
        elif isinstance(telemetry, Frame) and telemetry.kind == 'PONG':
            self._last_pong_s = now
        elif isinstance(telemetry, Frame) and telemetry.kind == 'BOOT':
            self._controller_ready = False
            self._host_estop_latched = True
            self._firmware_stopped = False
            self._estopped = True
            self._last_command_s = None
            self._command_timed_out = True
            self._firmware_identity, self._firmware_version = telemetry.fields
            try:
                validate_controller_boot(telemetry)
            except ProtocolError:
                self._controller_errors += 1
                self._last_controller_error = 'INCOMPATIBLE_BOOT'
                self._invalidate_controller(
                    'controller BOOT identity or protocol version is incompatible'
                )
                raise
            self._controller_ready = True
            self._send_velocity(0.0, 0.0)
            if self._release_estop_on_connect:
                if self._send(encode_estop(self._next_sequence(), False)):
                    self._host_estop_latched = False
                    self._estopped = self._firmware_stopped
            self.get_logger().info(
                f'controller boot: {self._firmware_identity} v{self._firmware_version}'
            )
        elif isinstance(telemetry, Frame) and telemetry.kind == 'ERR':
            self._controller_errors += 1
            self._last_controller_error = telemetry.fields[0]
            self._invalidate_controller(
                f'controller rejected command {telemetry.sequence}: '
                f'{self._last_controller_error}'
            )
        else:
            self._unknown_frames += 1

    def _record_telemetry_sequence(self, sequence: int) -> None:
        if self._last_telemetry_sequence is not None:
            expected = (self._last_telemetry_sequence + 1) & 0xFFFF
            if sequence != expected:
                self._sequence_gaps += (sequence - expected) & 0xFFFF
        self._last_telemetry_sequence = sequence

    def _publish_odometry(self, data: OdomTelemetry) -> None:
        if self._previous_left_ticks is None:
            left_delta_ticks = 0
            right_delta_ticks = 0
        else:
            left_delta_ticks = self._wrapped_tick_delta(
                data.left_ticks, self._previous_left_ticks
            )
            right_delta_ticks = self._wrapped_tick_delta(
                data.right_ticks, self._previous_right_ticks
            )
        self._previous_left_ticks = data.left_ticks
        self._previous_right_ticks = data.right_ticks

        radians_per_tick = 2.0 * math.pi / self._ticks_per_revolution
        left_delta_angle = left_delta_ticks * radians_per_tick
        right_delta_angle = right_delta_ticks * radians_per_tick
        self._left_joint_position += left_delta_angle
        self._right_joint_position += right_delta_angle
        left_distance = left_delta_angle * self._wheel_radius
        right_distance = right_delta_angle * self._wheel_radius
        distance = (left_distance + right_distance) / 2.0
        delta_yaw = (right_distance - left_distance) / self._wheel_separation
        heading = self._yaw + delta_yaw / 2.0
        self._x += distance * math.cos(heading)
        self._y += distance * math.sin(heading)
        self._yaw = math.atan2(
            math.sin(self._yaw + delta_yaw), math.cos(self._yaw + delta_yaw)
        )

        linear_velocity = (
            self._wheel_radius * (data.left_rad_s + data.right_rad_s) / 2.0
        )
        angular_velocity = (
            self._wheel_radius
            * (data.right_rad_s - data.left_rad_s)
            / self._wheel_separation
        )
        stamp = self.get_clock().now().to_msg()
        quaternion_z = math.sin(self._yaw / 2.0)
        quaternion_w = math.cos(self._yaw / 2.0)

        odom = Odometry()
        odom.header.stamp = stamp
        odom.header.frame_id = self._odom_frame
        odom.child_frame_id = self._base_frame
        odom.pose.pose.position.x = self._x
        odom.pose.pose.position.y = self._y
        odom.pose.pose.orientation.z = quaternion_z
        odom.pose.pose.orientation.w = quaternion_w
        odom.twist.twist.linear.x = linear_velocity
        odom.twist.twist.angular.z = angular_velocity
        odom.pose.covariance[0] = 0.02
        odom.pose.covariance[7] = 0.02
        odom.pose.covariance[14] = 1e6
        odom.pose.covariance[21] = 1e6
        odom.pose.covariance[28] = 1e6
        odom.pose.covariance[35] = 0.05
        odom.twist.covariance[0] = 0.05
        odom.twist.covariance[7] = 0.05
        odom.twist.covariance[14] = 1e6
        odom.twist.covariance[21] = 1e6
        odom.twist.covariance[28] = 1e6
        odom.twist.covariance[35] = 0.10
        self._odom_pub.publish(odom)

        battery = BatteryState()
        battery.header.stamp = stamp
        battery.voltage = data.battery_v if data.battery_v > 0.0 else math.nan
        battery.percentage = math.nan
        battery.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_UNKNOWN
        battery.power_supply_health = BatteryState.POWER_SUPPLY_HEALTH_UNKNOWN
        battery.power_supply_technology = BatteryState.POWER_SUPPLY_TECHNOLOGY_LION
        battery.present = data.battery_v > 0.0
        self._battery_pub.publish(battery)

        joints = JointState()
        joints.header.stamp = stamp
        joints.name = self._left_joints + self._right_joints
        joints.position = (
            [self._left_joint_position] * len(self._left_joints)
            + [self._right_joint_position] * len(self._right_joints)
        )
        joints.velocity = (
            [data.left_rad_s] * len(self._left_joints)
            + [data.right_rad_s] * len(self._right_joints)
        )
        self._joint_pub.publish(joints)

        if self._tf_broadcaster is not None:
            transform = TransformStamped()
            transform.header.stamp = stamp
            transform.header.frame_id = self._odom_frame
            transform.child_frame_id = self._base_frame
            transform.transform.translation.x = self._x
            transform.transform.translation.y = self._y
            transform.transform.rotation.z = quaternion_z
            transform.transform.rotation.w = quaternion_w
            self._tf_broadcaster.sendTransform(transform)

    def _publish_imu(self, data: ImuTelemetry) -> None:
        message = Imu()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = self._imu_frame
        message.orientation_covariance[0] = -1.0
        message.angular_velocity.x, message.angular_velocity.y, message.angular_velocity.z = (
            data.angular_velocity_rad_s
        )
        (
            message.linear_acceleration.x,
            message.linear_acceleration.y,
            message.linear_acceleration.z,
        ) = data.acceleration_m_s2
        message.angular_velocity_covariance[0] = 0.02
        message.angular_velocity_covariance[4] = 0.02
        message.angular_velocity_covariance[8] = 0.02
        message.linear_acceleration_covariance[0] = 0.04
        message.linear_acceleration_covariance[4] = 0.04
        message.linear_acceleration_covariance[8] = 0.04
        self._imu_pub.publish(message)

    def _publish_range(self, data: RangeTelemetry) -> None:
        message = Range()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = self._range_frame
        message.radiation_type = Range.ULTRASOUND
        message.field_of_view = self._range_fov
        message.min_range = self._range_min
        message.max_range = self._range_max
        if data.front_m < self._range_min:
            # sensor_msgs/Range uses -Inf for an obstacle closer than min range.
            message.range = -math.inf
        elif data.front_m > self._range_max:
            message.range = math.inf
        else:
            message.range = data.front_m
        self._range_pub.publish(message)

    def _on_cmd_vel(self, message: Twist) -> None:
        linear = message.linear.x
        angular = message.angular.z
        if not math.isfinite(linear) or not math.isfinite(angular):
            self.get_logger().error('discarded non-finite cmd_vel and commanded stop')
            self._send_velocity(0.0, 0.0)
            self._command_timed_out = True
            return
        linear = max(-self._max_linear, min(self._max_linear, linear))
        angular = max(-self._max_angular, min(self._max_angular, angular))
        left = (linear - angular * self._wheel_separation / 2.0) / self._wheel_radius
        right = (linear + angular * self._wheel_separation / 2.0) / self._wheel_radius
        peak = max(abs(left), abs(right))
        if peak > self._max_wheel_speed:
            scale = self._max_wheel_speed / peak
            linear *= scale
            angular *= scale
        if not self._controller_ready or self._estopped:
            self._send_velocity(0.0, 0.0)
            return
        if self._send_velocity(linear, angular):
            self._last_command_s = time.monotonic()
            self._command_timed_out = False

    def _on_emergency_stop(self, request, response):
        if not self._transport.is_open:
            response.success = False
            response.message = 'controller is disconnected'
            return response
        if not request.data and not self._controller_ready:
            response.success = False
            response.message = 'controller BOOT identity/version is not validated'
            return response
        sent = self._send(encode_estop(self._next_sequence(), bool(request.data)))
        if sent:
            self._host_estop_latched = bool(request.data)
            self._estopped = self._host_estop_latched or self._firmware_stopped
            self._send_velocity(0.0, 0.0)
            self._last_command_s = None
            self._command_timed_out = True
            response.success = True
            response.message = (
                'emergency stop engaged'
                if request.data
                else 'emergency stop released'
            )
        else:
            response.success = False
            response.message = 'failed to send emergency-stop command'
        return response

    def _on_estop_topic(self, message: Bool) -> None:
        """Apply the stable dashboard emergency-stop topic."""
        if not self._transport.is_open:
            self.get_logger().error(
                'cannot apply /wildebeest/estop: controller disconnected'
            )
            return
        if not message.data and not self._controller_ready:
            self.get_logger().error('cannot release estop before controller BOOT validation')
            return
        if self._send(encode_estop(self._next_sequence(), bool(message.data))):
            self._host_estop_latched = bool(message.data)
            self._estopped = self._host_estop_latched or self._firmware_stopped
            self._send_velocity(0.0, 0.0)
            self._last_command_s = None
            self._command_timed_out = True

    def _on_reset_odometry(self, request, response):
        del request
        self._x = self._y = self._yaw = 0.0
        self._left_joint_position = self._right_joint_position = 0.0
        self._previous_left_ticks = self._previous_right_ticks = None
        self.get_logger().info('local wheel-odometry origin reset')
        return response

    def _send_velocity(self, linear: float, angular: float) -> bool:
        try:
            frame = encode_cmd(self._next_sequence(), linear, angular)
        except ProtocolError as exc:
            self.get_logger().error(f'unsafe velocity command rejected: {exc}')
            return False
        return self._send(frame)

    def _send(self, frame: bytes) -> bool:
        if not self._transport.is_open:
            return False
        try:
            self._transport.write(frame)
            return True
        except TransportError as exc:
            self._handle_transport_error(exc)
            return False

    def _invalidate_controller(
        self, reason: str, close: bool = True, attempt_estop: bool = True
    ) -> None:
        """Fail closed and require a new transport connection plus valid BOOT."""
        if attempt_estop and self._transport.is_open:
            try:
                self._transport.write(
                    encode_estop(self._next_sequence(), True)
                )
            except TransportError:
                pass
        if close:
            self._transport.close()
        self._decoder.clear()
        self._previous_left_ticks = self._previous_right_ticks = None
        self._last_telemetry_sequence = None
        self._last_odom_s = None
        self._last_imu_s = None
        self._last_range_s = None
        self._last_pong_s = None
        self._controller_ready = False
        self._host_estop_latched = True
        self._firmware_stopped = False
        self._estopped = True
        self._last_command_s = None
        self._command_timed_out = True
        self.get_logger().error(reason)

    def _handle_transport_error(self, error: Exception, close: bool = True) -> None:
        self._transport_errors += 1
        self._invalidate_controller(
            f'controller transport error: {error}',
            close=close,
            attempt_estop=False,
        )

    def _publish_diagnostics(self) -> None:
        now = time.monotonic()
        connected = self._transport.is_open
        odom_age = math.inf if self._last_odom_s is None else now - self._last_odom_s
        pong_age = math.inf if self._last_pong_s is None else now - self._last_pong_s
        level = DiagnosticStatus.OK
        summary = 'controller healthy'
        if not connected:
            level, summary = DiagnosticStatus.ERROR, 'controller disconnected'
        elif not self._controller_ready:
            level, summary = DiagnosticStatus.ERROR, 'controller BOOT not validated'
        elif self._firmware_flags & MockController.FLAG_HARD_ESTOP:
            level, summary = DiagnosticStatus.ERROR, 'physical emergency stop engaged'
        elif self._firmware_flags & MockController.FLAG_SOFT_ESTOP:
            level, summary = DiagnosticStatus.ERROR, 'software emergency stop engaged'
        elif odom_age > self._telemetry_timeout:
            level, summary = DiagnosticStatus.ERROR, 'odometry telemetry stale'
        elif self._firmware_flags & MockController.FLAG_LOW_BATTERY:
            level, summary = DiagnosticStatus.ERROR, 'controller reports low battery'
        elif self._firmware_flags & MockController.FLAG_PROTOCOL_ERROR:
            level, summary = DiagnosticStatus.WARN, 'controller reports protocol errors'
        elif self._firmware_flags & (
            MockController.FLAG_IMU_ERROR | MockController.FLAG_RANGE_TIMEOUT
        ):
            level, summary = DiagnosticStatus.WARN, 'controller reports a sensor fault'
        elif self._firmware_flags & MockController.FLAG_WATCHDOG or self._command_timed_out:
            level, summary = DiagnosticStatus.WARN, 'motion watchdog stopped the base'
        elif self._rejected_frames:
            level, summary = DiagnosticStatus.WARN, 'serial frames have been rejected'

        status = DiagnosticStatus()
        status.level = level
        status.name = f'{self.get_namespace()}/wildebeest_base'.replace('//', '/')
        status.message = summary
        status.hardware_id = self._port if self._transport_mode == 'serial' else 'mock-controller'
        status.values = [
            KeyValue(key='transport', value=self._transport_mode),
            KeyValue(key='connected', value=str(connected).lower()),
            KeyValue(key='controller_ready', value=str(self._controller_ready).lower()),
            KeyValue(key='estop', value=str(self._estopped).lower()),
            KeyValue(
                key='host_estop_latched', value=str(self._host_estop_latched).lower()
            ),
            KeyValue(
                key='firmware_watchdog',
                value=str(
                    bool(self._firmware_flags & MockController.FLAG_WATCHDOG)
                ).lower(),
            ),
            KeyValue(key='firmware_flags', value=f'0x{self._firmware_flags:04X}'),
            KeyValue(key='firmware_identity', value=self._firmware_identity),
            KeyValue(key='firmware_version', value=self._firmware_version),
            KeyValue(key='odom_age_s', value=self._format_age(odom_age)),
            KeyValue(key='pong_age_s', value=self._format_age(pong_age)),
            KeyValue(key='battery_v', value=f'{self._battery_v:.3f}'),
            KeyValue(key='valid_frames', value=str(self._valid_frames)),
            KeyValue(key='rejected_frames', value=str(self._rejected_frames)),
            KeyValue(key='sequence_gaps', value=str(self._sequence_gaps)),
            KeyValue(key='transport_errors', value=str(self._transport_errors)),
            KeyValue(key='unknown_frames', value=str(self._unknown_frames)),
            KeyValue(key='controller_errors', value=str(self._controller_errors)),
            KeyValue(
                key='last_controller_error',
                value=self._last_controller_error or 'none',
            ),
        ]
        array = DiagnosticArray()
        array.header.stamp = self.get_clock().now().to_msg()
        array.status = [status]
        self._diagnostic_pub.publish(array)

    def shutdown_transport(self) -> None:
        """Best-effort motion stop before closing the controller link."""
        if self._transport.is_open:
            self._send_velocity(0.0, 0.0)
            if self._estop_on_shutdown:
                self._send(encode_estop(self._next_sequence(), True))
            self._transport.close()

    def _next_sequence(self) -> int:
        sequence = self._sequence
        self._sequence = (self._sequence + 1) & 0xFFFF
        return sequence

    @staticmethod
    def _wrapped_tick_delta(current: int, previous: int) -> int:
        return ((current - previous + 2**31) % 2**32) - 2**31

    @staticmethod
    def _format_age(age: float) -> str:
        return 'never' if not math.isfinite(age) else f'{age:.3f}'


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = SerialBridge()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.shutdown_transport()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
