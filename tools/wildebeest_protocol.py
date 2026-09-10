"""Dependency-free codec for the Wildebeest base-controller protocol."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

MAX_FRAME_BYTES = 128
_TYPE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,15}$")


class ProtocolError(ValueError):
    """Raised when a frame fails syntax, schema, or integrity validation."""


@dataclass(frozen=True, slots=True)
class Frame:
    kind: str
    sequence: int
    fields: tuple[str, ...] = ()

    def integer(self, index: int, minimum: int, maximum: int) -> int:
        try:
            text = self.fields[index]
        except IndexError as exc:
            raise ProtocolError(f"missing field {index} in {self.kind}") from exc
        if not re.fullmatch(r"-?(0|[1-9][0-9]*)", text):
            raise ProtocolError(f"field {index} is not a canonical integer")
        value = int(text)
        if not minimum <= value <= maximum:
            raise ProtocolError(f"field {index} outside [{minimum}, {maximum}]")
        return value


def crc16_ccitt_false(data: bytes) -> int:
    """CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, xorout 0)."""

    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def encode_frame(kind: str, sequence: int, *fields: object) -> bytes:
    if not _TYPE_RE.fullmatch(kind):
        raise ProtocolError(f"invalid frame type: {kind!r}")
    if isinstance(sequence, bool) or not isinstance(sequence, int):
        raise ProtocolError("sequence must be an unsigned 16-bit integer")
    if not 0 <= sequence <= 65535:
        raise ProtocolError("sequence must be an unsigned 16-bit integer")
    rendered = [kind, str(sequence)]
    for value in fields:
        text = str(value)
        if not text or any(char in text for char in ",*\r\n") or not text.isascii():
            raise ProtocolError(f"unsafe field: {text!r}")
        rendered.append(text)
    body = ",".join(rendered).encode("ascii")
    frame = b"@" + body + f"*{crc16_ccitt_false(body):04X}\n".encode("ascii")
    if len(frame) > MAX_FRAME_BYTES:
        raise ProtocolError("encoded frame exceeds maximum length")
    return frame


def decode_frame(raw: bytes | str) -> Frame:
    if isinstance(raw, str):
        try:
            raw = raw.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ProtocolError("frame is not ASCII") from exc
    if len(raw) > MAX_FRAME_BYTES:
        raise ProtocolError("frame exceeds maximum length")
    line = raw.rstrip(b"\r\n")
    if not line.startswith(b"@") or line.count(b"*") != 1:
        raise ProtocolError("frame must be @BODY*CRC")
    body, supplied_crc = line[1:].split(b"*", 1)
    if not re.fullmatch(rb"[0-9A-Fa-f]{4}", supplied_crc):
        raise ProtocolError("CRC must contain exactly four hexadecimal digits")
    actual = crc16_ccitt_false(body)
    expected = int(supplied_crc, 16)
    if actual != expected:
        raise ProtocolError(f"CRC mismatch: received {expected:04X}, calculated {actual:04X}")
    try:
        parts = body.decode("ascii").split(",")
    except UnicodeDecodeError as exc:
        raise ProtocolError("frame is not ASCII") from exc
    if len(parts) < 2 or not _TYPE_RE.fullmatch(parts[0]):
        raise ProtocolError("invalid frame type or missing sequence")
    if not re.fullmatch(r"(0|[1-9][0-9]*)", parts[1]):
        raise ProtocolError("sequence is not a canonical unsigned integer")
    sequence = int(parts[1])
    if sequence > 65535:
        raise ProtocolError("sequence exceeds 16 bits")
    return Frame(parts[0], sequence, tuple(parts[2:]))


class StreamDecoder:
    """Incremental bounded decoder that re-synchronizes at the next '@'."""

    def __init__(self, max_frame_bytes: int = MAX_FRAME_BYTES) -> None:
        self.max_frame_bytes = max_frame_bytes
        self._buffer = bytearray()
        self.dropped_frames = 0

    def feed(self, chunk: bytes) -> list[Frame]:
        frames: list[Frame] = []
        for byte in chunk:
            if byte == ord("@"):
                if self._buffer:
                    self.dropped_frames += 1
                self._buffer = bytearray(b"@")
                continue
            if not self._buffer:
                continue
            self._buffer.append(byte)
            if len(self._buffer) > self.max_frame_bytes:
                self._buffer.clear()
                self.dropped_frames += 1
                continue
            if byte == ord("\n"):
                try:
                    frames.append(decode_frame(bytes(self._buffer)))
                except ProtocolError:
                    self.dropped_frames += 1
                self._buffer.clear()
        return frames


def validate_schema(frame: Frame) -> Frame:
    """Validate field counts and safe numeric ranges for a known frame."""

    counts = {"CMD": 2, "PING": 0, "ESTOP": 1, "ODOM": 6, "IMU": 6,
              "RANGE": 1, "PONG": 0, "BOOT": 2, "ERR": 1}
    if frame.kind not in counts:
        raise ProtocolError(f"unknown frame type: {frame.kind}")
    if len(frame.fields) != counts[frame.kind]:
        raise ProtocolError(f"{frame.kind} requires {counts[frame.kind]} fields")
    if frame.kind == "CMD":
        frame.integer(0, -450, 450)
        frame.integer(1, -1800, 1800)
    elif frame.kind == "ESTOP":
        frame.integer(0, 0, 1)
    elif frame.kind == "ODOM":
        frame.integer(0, -(2**31), 2**31 - 1)
        frame.integer(1, -(2**31), 2**31 - 1)
        frame.integer(2, -100_000, 100_000)
        frame.integer(3, -100_000, 100_000)
        frame.integer(4, 0, 20_000)
        frame.integer(5, 0, 0xFFFF)
    elif frame.kind == "IMU":
        for index in range(3):
            frame.integer(index, -16_000, 16_000)
        for index in range(3, 6):
            frame.integer(index, -2_000_000, 2_000_000)
    elif frame.kind == "RANGE":
        frame.integer(0, 0, 2_000)
    return frame


def encode_many(frames: Iterable[Frame]) -> bytes:
    return b"".join(encode_frame(frame.kind, frame.sequence, *frame.fields) for frame in frames)
