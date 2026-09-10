import test from "node:test";
import assert from "node:assert/strict";
import { batteryPercent, preferredFreshSource, quaternionYaw, rosType, scanPoints } from "../telemetry.mjs";

test("quaternion yaw handles a quarter turn", () => {
  assert.ok(Math.abs(quaternionYaw({ z: Math.SQRT1_2, w: Math.SQRT1_2 }) - Math.PI / 2) < 1e-9);
});
test("battery percentage clamps and detects bad calibration", () => {
  assert.equal(batteryPercent(7.5, 6.6, 8.4), 50);
  assert.equal(batteryPercent(9, 6.6, 8.4), 100);
  assert.equal(batteryPercent(7, 8, 8), null);
});
test("scan filters invalid and out-of-range values", () => {
  const points = scanPoints({ ranges:[NaN,.01,1,20], range_min:.02, range_max:10, angle_min:0, angle_increment:1 });
  assert.equal(points.length, 1); assert.equal(points[0].range, 1);
});
test("message types differ only where ROS requires", () => {
  assert.equal(rosType(1,"std_msgs/Bool","std_msgs/msg/Bool"), "std_msgs/Bool");
  assert.equal(rosType(2,"std_msgs/Bool","std_msgs/msg/Bool"), "std_msgs/msg/Bool");
});
test("odometry selection prefers fresh fused data and falls back explicitly", () => {
  const order = ["odom_filtered", "odom_wheel", "odom_sim"];
  assert.equal(preferredFreshSource({ odom_filtered: 990, odom_wheel: 995 }, order, 1000, 100), "odom_filtered");
  assert.equal(preferredFreshSource({ odom_filtered: 800, odom_wheel: 995 }, order, 1000, 100), "odom_wheel");
  assert.equal(preferredFreshSource({ odom_sim: 950 }, order, 1000, 100), "odom_sim");
  assert.equal(preferredFreshSource({}, order, 1000, 100), null);
});
