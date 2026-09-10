"""Republish Gazebo's generic Range message as the hardware sonar contract."""

import math

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Range

from .range_contract import normalize_range


class RangeContractAdapter(Node):
    """Make simulation and physical `/range/front` messages interchangeable."""

    def __init__(self) -> None:
        super().__init__('range_contract_adapter')
        self.declare_parameter('input_topic', '/range/front_raw')
        self.declare_parameter('output_topic', '/range/front')
        self.declare_parameter('frame_id', 'ultrasonic_front_link')
        self.declare_parameter('field_of_view', 0.26)
        self.declare_parameter('min_range', 0.02)
        self.declare_parameter('max_range', 2.0)
        self._frame_id = str(self.get_parameter('frame_id').value)
        self._field_of_view = float(self.get_parameter('field_of_view').value)
        self._min_range = float(self.get_parameter('min_range').value)
        self._max_range = float(self.get_parameter('max_range').value)
        if not self._frame_id:
            raise ValueError('frame_id must not be empty')
        if not math.isfinite(self._field_of_view) or self._field_of_view <= 0.0:
            raise ValueError('field_of_view must be finite and positive')
        normalize_range(self._min_range, self._min_range, self._max_range)
        output_topic = str(self.get_parameter('output_topic').value)
        input_topic = str(self.get_parameter('input_topic').value)
        self._publisher = self.create_publisher(
            Range, output_topic, qos_profile_sensor_data
        )
        self._subscription = self.create_subscription(
            Range, input_topic, self._on_range, qos_profile_sensor_data
        )

    def _on_range(self, source: Range) -> None:
        try:
            value = normalize_range(
                float(source.range), self._min_range, self._max_range
            )
        except ValueError:
            self.get_logger().warning('discarded non-finite simulated range')
            return
        message = Range()
        message.header = source.header
        message.header.frame_id = self._frame_id
        message.radiation_type = Range.ULTRASOUND
        message.field_of_view = self._field_of_view
        message.min_range = self._min_range
        message.max_range = self._max_range
        message.range = value
        self._publisher.publish(message)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RangeContractAdapter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
