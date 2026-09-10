"""ROS node continuously driving Gazebo through a fail-safe Twist gate."""

import math
import time

from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool

from .gate import SafetyTwistGate


class SafetyTwistGateNode(Node):
    """Insert an independent wall-clock watchdog before Gazebo DiffDrive."""

    def __init__(self) -> None:
        super().__init__('simulation_safety_twist_gate')
        self.declare_parameter('input_topic', '/cmd_vel')
        self.declare_parameter('output_topic', '/cmd_vel/sim_safe')
        self.declare_parameter('estop_topic', '/wildebeest/estop')
        self.declare_parameter('timeout_s', 0.25)
        self.declare_parameter('publish_rate_hz', 40.0)
        self.declare_parameter('max_linear_m_s', 0.45)
        self.declare_parameter('max_angular_rad_s', 1.8)
        timeout = float(self.get_parameter('timeout_s').value)
        rate = float(self.get_parameter('publish_rate_hz').value)
        if rate <= 0.0 or not math.isfinite(rate):
            raise ValueError('publish_rate_hz must be finite and positive')
        self._gate = SafetyTwistGate(
            timeout_s=timeout,
            max_linear_m_s=float(self.get_parameter('max_linear_m_s').value),
            max_angular_rad_s=float(self.get_parameter('max_angular_rad_s').value),
        )
        input_topic = str(self.get_parameter('input_topic').value)
        output_topic = str(self.get_parameter('output_topic').value)
        estop_topic = str(self.get_parameter('estop_topic').value)
        self._publisher = self.create_publisher(Twist, output_topic, 10)
        self._command_subscriber = self.create_subscription(
            Twist, input_topic, self._on_command, 10
        )
        self._estop_subscriber = self.create_subscription(
            Bool, estop_topic, self._on_estop, 10
        )
        self._timer = self.create_timer(1.0 / rate, self._publish_safe_command)

    def _on_command(self, message: Twist) -> None:
        if not self._gate.receive(
            message.linear.x, message.angular.z, time.monotonic()
        ):
            self.get_logger().warning('simulation safety gate rejected cmd_vel')

    def _on_estop(self, message: Bool) -> None:
        self._gate.set_estop(bool(message.data))
        self._publish_zero()

    def _publish_safe_command(self) -> None:
        linear, angular = self._gate.output(time.monotonic())
        message = Twist()
        message.linear.x = linear
        message.angular.z = angular
        self._publisher.publish(message)

    def _publish_zero(self) -> None:
        self._publisher.publish(Twist())

    def stop(self) -> None:
        """Invalidate motion and send a best-effort final zero."""

        self._gate.invalidate()
        self._publish_zero()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SafetyTwistGateNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
