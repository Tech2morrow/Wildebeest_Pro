#!/usr/bin/env python3
"""Assert that a container's mock base completed its safety handshake.

This probe intentionally uses only standard ROS message packages.  It verifies
that the launched graph is producing wheel odometry and that the base diagnostic
reports both an open transport and an exact, validated controller BOOT frame.
"""

import os
import sys
import time


TIMEOUT_S = 20.0


def diagnostic_is_ready(message):
    for status in message.status:
        values = {item.key: item.value for item in status.values}
        if (
            values.get("connected") == "true"
            and values.get("controller_ready") == "true"
        ):
            return True
    return False


def check_ros1():
    import rospy
    from diagnostic_msgs.msg import DiagnosticArray
    from nav_msgs.msg import Odometry

    rospy.init_node("wildebeest_ci_probe", anonymous=True, disable_signals=True)
    deadline = time.monotonic() + TIMEOUT_S
    ready = False
    while not ready and time.monotonic() < deadline:
        remaining = max(0.1, deadline - time.monotonic())
        try:
            message = rospy.wait_for_message(
                "/diagnostics", DiagnosticArray, timeout=min(1.0, remaining)
            )
        except rospy.ROSException:
            continue
        ready = diagnostic_is_ready(message)
    if not ready:
        raise RuntimeError("ROS 1 mock controller did not validate its BOOT handshake")
    remaining = max(0.1, deadline - time.monotonic())
    rospy.wait_for_message("/wheel/odometry", Odometry, timeout=remaining)


def check_ros2():
    import rclpy
    from diagnostic_msgs.msg import DiagnosticArray
    from nav_msgs.msg import Odometry
    from rclpy.node import Node

    rclpy.init(args=None)
    node = Node("wildebeest_ci_probe")
    state = {"ready": False, "odometry": False}

    def diagnostics_callback(message):
        state["ready"] = state["ready"] or diagnostic_is_ready(message)

    def odometry_callback(_message):
        state["odometry"] = True

    subscriptions = [
        node.create_subscription(
            DiagnosticArray, "/diagnostics", diagnostics_callback, 10
        ),
        node.create_subscription(
            Odometry, "/wheel/odometry", odometry_callback, 10
        ),
    ]
    deadline = time.monotonic() + TIMEOUT_S
    try:
        while not all(state.values()) and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.25)
    finally:
        # Keep subscriptions alive through the spin, then release ROS resources.
        subscriptions.clear()
        node.destroy_node()
        rclpy.shutdown()
    if not state["ready"]:
        raise RuntimeError("ROS 2 mock controller did not validate its BOOT handshake")
    if not state["odometry"]:
        raise RuntimeError("ROS 2 mock controller did not publish wheel odometry")


def main():
    ros_version = os.environ.get("ROS_VERSION")
    if ros_version == "1":
        check_ros1()
    elif ros_version == "2":
        check_ros2()
    else:
        raise RuntimeError("ROS_VERSION must be 1 or 2")
    print("Mock controller ready; live wheel odometry received.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # Keep CI output concise and actionable.
        print("Smoke check failed: {}".format(exc), file=sys.stderr)
        sys.exit(1)
