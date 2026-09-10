import { batteryPercent, preferredFreshSource, quaternionYaw, rosType, scanPoints } from "./telemetry.mjs";

const $ = (selector) => document.querySelector(selector);
const state = { socket: null, connected: false, estop: false, command: { linear: 0, angular: 0 }, last: {}, scan: null, pose: { x: 0, y: 0, yaw: 0 }, keys: new Set(), drag: false };

class Rosbridge {
  connect(url) {
    return new Promise((resolve, reject) => {
      const socket = new WebSocket(url);
      const timeout = setTimeout(() => { socket.close(); reject(new Error("Connection timed out")); }, 5000);
      socket.onopen = () => { clearTimeout(timeout); this.socket = socket; resolve(); };
      socket.onerror = () => { clearTimeout(timeout); reject(new Error("WebSocket connection failed")); };
      socket.onmessage = (event) => this.onMessage?.(JSON.parse(event.data));
      socket.onclose = () => this.onClose?.();
    });
  }
  send(payload) {
    if (this.socket?.readyState !== WebSocket.OPEN) return false;
    this.socket.send(JSON.stringify(payload));
    return true;
  }
  subscribe(topic) { return this.send({ op: "subscribe", id: `wb:${topic}`, topic, throttle_rate: 50, queue_length: 1 }); }
  advertise(topic, type) { return this.send({ op: "advertise", topic, type }); }
  publish(topic, msg) { return this.send({ op: "publish", topic, msg }); }
  close() { this.socket?.close(); }
}

const bridge = new Rosbridge();
const topics = { "/odometry/filtered": "odom_filtered", "/wheel/odometry": "odom_wheel", "/odom": "odom_sim", "/scan": "scan", "/imu/data_raw": "imu", "/gps/fix": "gps", "/range/front": "range", "/battery_state": "battery" };
const odometryPriority = ["odom_filtered", "odom_wheel", "odom_sim"];
const odometryLabels = { odom_filtered: "FUSED", odom_wheel: "WHEEL", odom_sim: "SIM" };

function log(message, level = "info") {
  const item = document.createElement("li");
  item.className = level;
  item.innerHTML = `<time>${new Date().toLocaleTimeString([], { hour12: false })}</time><span></span>`;
  item.lastElementChild.textContent = message;
  const list = $("#event-log");
  list.prepend(item);
  while (list.children.length > 40) list.lastElementChild.remove();
}

function setConnection(connected, text) {
  state.connected = connected;
  $("#connection-dot").classList.toggle("connected", connected);
  $("#connect").textContent = connected ? "Disconnect" : "Connect";
  $("#mission-state").textContent = text;
}

function subscribeAll() {
  Object.keys(topics).forEach((topic) => bridge.subscribe(topic));
  const major = $("#ros-major").value;
  bridge.advertise("/cmd_vel/remote", rosType(major, "geometry_msgs/Twist", "geometry_msgs/msg/Twist"));
  bridge.advertise("/wildebeest/estop", rosType(major, "std_msgs/Bool", "std_msgs/msg/Bool"));
}

$("#connection-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.connected) { publishCommand(0, 0); bridge.close(); return; }
  setConnection(false, "Connecting to rosbridge…");
  try {
    bridge.onMessage = receive;
    bridge.onClose = () => { setConnection(false, "Connection closed — drive output disabled"); stopDrive(); log("rosbridge disconnected", "warn"); };
    await bridge.connect($("#endpoint").value.trim());
    setConnection(true, `Connected to ${$("#endpoint").value.trim()}`);
    subscribeAll();
    log("rosbridge connected");
  } catch (error) { setConnection(false, error.message); log(error.message, "error"); }
});

function receive(envelope) {
  if (envelope.op !== "publish") return;
  const key = topics[envelope.topic];
  if (!key) return;
  state.last[key] = performance.now();
  updateTopicHealth();
  const message = envelope.msg || {};
  if (key.startsWith("odom_")) {
    const selected = preferredFreshSource(state.last, odometryPriority, performance.now(), 2500);
    if (selected !== key) return;
    const twist = message.twist?.twist || message.twist || {};
    const pose = message.pose?.pose || message.pose || {};
    $("#odom-source").textContent = odometryLabels[key];
    state.pose = { x: Number(pose.position?.x) || 0, y: Number(pose.position?.y) || 0, yaw: quaternionYaw(pose.orientation) };
    $("#linear-speed").textContent = (Number(twist.linear?.x) || 0).toFixed(2);
    $("#pose-x").textContent = state.pose.x.toFixed(2); $("#pose-y").textContent = state.pose.y.toFixed(2);
    $("#pose-yaw").textContent = `${(state.pose.yaw * 180 / Math.PI).toFixed(1)}°`; $("#heading").textContent = (state.pose.yaw * 180 / Math.PI).toFixed(1);
  } else if (key === "scan") { state.scan = message; drawScan();
  } else if (key === "imu") { $("#turn-rate").textContent = (Number(message.angular_velocity?.z) || 0).toFixed(2);
  } else if (key === "range") { const value = Number(message.range); $("#range-front").textContent = Number.isFinite(value) ? value.toFixed(2) : "--"; $("#range-state").textContent = value < 0.35 ? "Obstacle close" : "Path clear";
  } else if (key === "battery") {
    const voltage = Number(message.voltage); const pct = Number.isFinite(Number(message.percentage)) && Number(message.percentage) >= 0 ? Number(message.percentage) * 100 : batteryPercent(voltage);
    $("#battery-voltage").textContent = Number.isFinite(voltage) ? voltage.toFixed(2) : "--.--";
    $("#battery-percent").textContent = pct == null ? "--" : Math.round(pct); $("#battery-fill").style.width = `${pct || 0}%`;
    $("#battery-health").textContent = pct == null ? "NO DATA" : pct < 15 ? "CRITICAL" : pct < 30 ? "LOW" : "NOMINAL";
  }
}

function updateTopicHealth() {
  const now = performance.now();
  document.querySelectorAll(".systems li").forEach((item) => {
    const fresh = now - (state.last[item.dataset.topic] || -Infinity) < 2500;
    item.classList.toggle("fresh", fresh); item.querySelector("i").textContent = fresh ? "ONLINE" : "OFFLINE";
  });
}
setInterval(updateTopicHealth, 1000);

function publishCommand(linear = state.command.linear, angular = state.command.angular) {
  state.command = { linear, angular };
  $("#linear-command").textContent = linear.toFixed(2);
  if (state.connected && !state.estop) bridge.publish("/cmd_vel/remote", { linear: { x: linear, y: 0, z: 0 }, angular: { x: 0, y: 0, z: angular } });
}
function stopDrive() { state.drag = false; state.keys.clear(); state.command = { linear: 0, angular: 0 }; $("#stick").style.transform = "translate(0px,0px)"; publishCommand(0, 0); }
setInterval(() => { if (state.connected && (state.drag || state.keys.size)) publishCommand(); }, 100);

function joystickAt(clientX, clientY) {
  const pad = $("#joystick"); const rect = pad.getBoundingClientRect();
  let x = clientX - (rect.left + rect.width / 2); let y = clientY - (rect.top + rect.height / 2); const radius = rect.width * .32;
  const magnitude = Math.hypot(x, y); if (magnitude > radius) { x *= radius / magnitude; y *= radius / magnitude; }
  $("#stick").style.transform = `translate(${x}px,${y}px)`;
  publishCommand(-y / radius * Number($("#speed-limit").value), -x / radius * Number($("#turn-limit").value));
}
$("#joystick").addEventListener("pointerdown", (e) => { if (state.estop) return; state.drag = true; e.currentTarget.setPointerCapture(e.pointerId); joystickAt(e.clientX, e.clientY); });
$("#joystick").addEventListener("pointermove", (e) => { if (state.drag) joystickAt(e.clientX, e.clientY); });
$("#joystick").addEventListener("pointerup", stopDrive); $("#joystick").addEventListener("pointercancel", stopDrive);

function keyboardCommand() { const s = Number($("#speed-limit").value), t = Number($("#turn-limit").value); publishCommand((state.keys.has("w") ? s : 0) + (state.keys.has("s") ? -s : 0), (state.keys.has("a") ? t : 0) + (state.keys.has("d") ? -t : 0)); }
window.addEventListener("keydown", (event) => { if (/INPUT|SELECT/.test(document.activeElement?.tagName)) return; const key = event.key.toLowerCase(); if (key === " ") { event.preventDefault(); engageEstop(); return; } if (["w","a","s","d"].includes(key) && !state.estop) { state.keys.add(key); keyboardCommand(); } });
window.addEventListener("keyup", (event) => { state.keys.delete(event.key.toLowerCase()); keyboardCommand(); });
window.addEventListener("blur", stopDrive);

function engageEstop() {
  // Send a final zero while the local drive gate is still open, then latch the
  // browser-side stop regardless of network state.
  stopDrive();
  state.estop = true;
  const delivered = bridge.publish("/wildebeest/estop", { data: true });
  $("#estop").classList.add("active");
  $("#estop").textContent = delivered ? "Stop request sent — verify robot" : "LOCAL STOP — NOT DELIVERED";
  log(delivered ? "Software stop request sent; verify diagnostics and physical state" : "Software stop was not delivered because rosbridge is offline", delivered ? "error" : "warn");
}
$("#estop").addEventListener("click", () => {
  if (!state.estop) { engageEstop(); return; }
  if (!confirm("Request software-stop release? Confirm the area is safe and the physical E-stop is released.")) return;
  if (!state.connected || !bridge.publish("/wildebeest/estop", { data: false })) {
    $("#estop").textContent = "LOCAL STOP — RELEASE NOT DELIVERED";
    log("Software-stop release was not delivered; local stop remains latched", "warn");
    return;
  }
  state.estop = false;
  $("#estop").classList.remove("active");
  $("#estop").innerHTML = "<span></span>Release sent — verify robot";
  log("Software-stop release request sent; a fresh drive command is required", "warn");
});

function drawScan() {
  const canvas = $("#scan-canvas"), rect = canvas.getBoundingClientRect(), ratio = devicePixelRatio || 1;
  if (canvas.width !== Math.round(rect.width * ratio) || canvas.height !== Math.round(rect.height * ratio)) { canvas.width = Math.round(rect.width * ratio); canvas.height = Math.round(rect.height * ratio); }
  const ctx = canvas.getContext("2d"); ctx.setTransform(ratio,0,0,ratio,0,0); ctx.clearRect(0,0,rect.width,rect.height);
  const cx = rect.width / 2, cy = rect.height * .62, scale = Math.min(rect.width,rect.height) / 11;
  ctx.fillStyle = "rgba(82,232,200,.84)"; for (const point of scanPoints(state.scan)) { const x = cx + point.y * scale, y = cy - point.x * scale; ctx.beginPath(); ctx.arc(x,y,point.range < .5 ? 2.4 : 1.35,0,Math.PI*2); ctx.fill(); }
  ctx.save(); ctx.translate(cx,cy); ctx.rotate(-state.pose.yaw); ctx.fillStyle="#f3bd4c"; ctx.strokeStyle="#07131f"; ctx.lineWidth=2; ctx.beginPath(); ctx.moveTo(0,-16);ctx.lineTo(11,12);ctx.lineTo(0,7);ctx.lineTo(-11,12);ctx.closePath();ctx.fill();ctx.stroke();ctx.restore();
}
new ResizeObserver(drawScan).observe($("#scan-canvas")); drawScan();

for (const [input, output, unit] of [["#speed-limit","#speed-output","m/s"],["#turn-limit","#turn-output","rad/s"]]) $(input).addEventListener("input", (e) => { $(output).textContent = `${Number(e.target.value).toFixed(2)} ${unit}`; });
$("#settings").addEventListener("click", () => $("#settings-dialog").showModal());
$("#save-camera").addEventListener("click", () => { const url = $("#camera-url").value.trim(); localStorage.setItem("wildebeest.camera", url); const image = $("#camera-stream"); image.src = url; image.classList.toggle("active", Boolean(url)); $("#camera-state").textContent = url ? "STREAM SET" : "STREAM OFF"; });
const savedCamera = localStorage.getItem("wildebeest.camera") || ""; $("#camera-url").value = savedCamera; if (savedCamera) { $("#camera-stream").src=savedCamera; $("#camera-stream").classList.add("active"); $("#camera-state").textContent="STREAM SET"; }
$("#clear-log").addEventListener("click", () => { $("#event-log").innerHTML=""; log("Log cleared"); });
setInterval(() => { $("#clock").textContent = new Date().toLocaleTimeString([], { hour12: false }); }, 250);
