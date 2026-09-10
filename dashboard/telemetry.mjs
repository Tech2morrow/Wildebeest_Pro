export const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value));

export function quaternionYaw(q = {}) {
  const x = Number(q.x) || 0;
  const y = Number(q.y) || 0;
  const z = Number(q.z) || 0;
  const w = Number(q.w) || 1;
  return Math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z));
}

export function batteryPercent(voltage, minimum = 6.6, maximum = 8.4) {
  if (!Number.isFinite(voltage) || maximum <= minimum) return null;
  return clamp(((voltage - minimum) / (maximum - minimum)) * 100, 0, 100);
}

export function scanPoints(scan, maxPoints = 360) {
  if (!scan || !Array.isArray(scan.ranges)) return [];
  const stride = Math.max(1, Math.ceil(scan.ranges.length / maxPoints));
  const minimum = Number(scan.range_min) || 0.02;
  const maximum = Number(scan.range_max) || 12;
  const start = Number(scan.angle_min) || 0;
  const increment = Number(scan.angle_increment) || 0;
  const points = [];
  for (let index = 0; index < scan.ranges.length; index += stride) {
    const range = Number(scan.ranges[index]);
    if (!Number.isFinite(range) || range < minimum || range > maximum) continue;
    const angle = start + index * increment;
    points.push({ x: Math.cos(angle) * range, y: Math.sin(angle) * range, range });
  }
  return points;
}

export function rosType(major, ros1, ros2) {
  return String(major) === "1" ? ros1 : ros2;
}

export function preferredFreshSource(lastSeen, priority, now, maximumAgeMs) {
  return priority.find((source) => {
    const timestamp = Number(lastSeen[source]);
    return Number.isFinite(timestamp) && now - timestamp >= 0 && now - timestamp < maximumAgeMs;
  }) || null;
}
