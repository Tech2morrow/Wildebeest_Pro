#!/usr/bin/env python3
"""Small deterministic base-controller simulator for integration testing.

Use `--tcp 8765` with a bridge transport that supports `socket://127.0.0.1:8765`,
or `--demo` to print a short valid telemetry stream without ROS or hardware.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import select
import socket
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wildebeest_protocol import Frame, ProtocolError, StreamDecoder, encode_frame, validate_schema


class BaseSimulation:
    def __init__(self) -> None:
        self.left_ticks = 0.0
        self.right_ticks = 0.0
        self.left_rad_s = 0.0
        self.right_rad_s = 0.0
        self.target_left = 0.0
        self.target_right = 0.0
        self.estop = False
        self.last_command = time.monotonic()
        self.sequence = 0
        self.ticks_per_rev = 600
        self.wheel_radius = 0.033622
        self.wheel_separation = 0.121843

    def receive(self, frame: Frame) -> list[bytes]:
        validate_schema(frame)
        if frame.kind == "CMD":
            linear = frame.integer(0, -450, 450) / 1000.0
            angular = frame.integer(1, -1800, 1800) / 1000.0
            self.target_left = (linear - angular * self.wheel_separation / 2) / self.wheel_radius
            self.target_right = (linear + angular * self.wheel_separation / 2) / self.wheel_radius
            self.last_command = time.monotonic()
        elif frame.kind == "ESTOP":
            self.estop = bool(frame.integer(0, 0, 1))
        elif frame.kind == "PING":
            return [encode_frame("PONG", frame.sequence)]
        return []

    def step(self, dt: float) -> list[bytes]:
        watchdog = time.monotonic() - self.last_command > 0.3
        enabled = not watchdog and not self.estop
        target_l = self.target_left if enabled else 0.0
        target_r = self.target_right if enabled else 0.0
        alpha = min(1.0, dt / 0.12)
        self.left_rad_s += (target_l - self.left_rad_s) * alpha
        self.right_rad_s += (target_r - self.right_rad_s) * alpha
        self.left_ticks += self.left_rad_s * dt * self.ticks_per_rev / (2 * math.pi)
        self.right_ticks += self.right_rad_s * dt * self.ticks_per_rev / (2 * math.pi)
        flags = (1 if watchdog else 0) | (4 if self.estop else 0)
        seq = self.sequence & 0xFFFF
        self.sequence += 3
        odom = encode_frame("ODOM", seq, round(self.left_ticks), round(self.right_ticks),
                            round(self.left_rad_s * 1000), round(self.right_rad_s * 1000),
                            7800, flags)
        imu = encode_frame("IMU", (seq + 1) & 0xFFFF, 0, 0, 1000, 0, 0,
                           round((self.right_rad_s - self.left_rad_s) * self.wheel_radius /
                                 self.wheel_separation * 1000))
        range_frame = encode_frame("RANGE", (seq + 2) & 0xFFFF, 800)
        return [odom, imu, range_frame]


def run_demo(seconds: float) -> int:
    simulation = BaseSimulation()
    simulation.receive(validate_schema(Frame("CMD", 1, ("180", "300"))))
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        for payload in simulation.step(0.05):
            sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()
        time.sleep(0.05)
    return 0


def run_tcp(port: int, rate_hz: float) -> int:
    decoder = StreamDecoder()
    simulation = BaseSimulation()
    period = 1.0 / rate_hz
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", port))
        server.listen(1)
        print(f"mock MCU listening on socket://127.0.0.1:{port}", file=sys.stderr)
        client, address = server.accept()
        print(f"bridge connected from {address[0]}:{address[1]}", file=sys.stderr)
        with client:
            client.setblocking(False)
            last = time.monotonic()
            while True:
                now = time.monotonic()
                readable, _, _ = select.select([client], [], [], max(0.0, period - (now - last)))
                if readable:
                    data = client.recv(1024)
                    if not data:
                        return 0
                    for frame in decoder.feed(data):
                        try:
                            for response in simulation.receive(frame):
                                client.sendall(response)
                        except ProtocolError as exc:
                            client.sendall(encode_frame("ERR", frame.sequence, "SCHEMA"))
                            print(f"rejected {frame}: {exc}", file=sys.stderr)
                now = time.monotonic()
                if now - last >= period:
                    dt = min(now - last, 0.25)
                    last = now
                    for payload in simulation.step(dt):
                        client.sendall(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--demo", action="store_true", help="emit telemetry to stdout")
    mode.add_argument("--tcp", type=int, metavar="PORT", help="serve one TCP bridge client")
    parser.add_argument("--seconds", type=float, default=1.0, help="demo duration")
    parser.add_argument("--rate", type=float, default=20.0, help="telemetry rate in hertz")
    args = parser.parse_args()
    if args.rate <= 0 or args.seconds <= 0:
        parser.error("--rate and --seconds must be positive")
    try:
        return run_demo(args.seconds) if args.demo else run_tcp(args.tcp, args.rate)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
