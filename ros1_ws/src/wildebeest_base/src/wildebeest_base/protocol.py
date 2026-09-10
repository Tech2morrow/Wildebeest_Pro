"""Versioned, bounded serial protocol shared by the host and Arduino firmware.

Frames are ASCII and newline terminated::

    @TYPE,seq,field...*CRC16\n

The CRC is CRC-16/CCITT-FALSE over the bytes strictly between ``@`` and ``*``.
This module deliberately has no ROS dependencies so it can be unit tested on any
developer machine and reused by commissioning tools.
"""

from dataclasses import dataclass
from typing import Iterable, List, Mapping, Sequence, Tuple, Union

MAX_FRAME_BYTES = 128
# Compatibility alias for older callers; protocol v1 names the wire limit in bytes.
MAX_LINE_BYTES = MAX_FRAME_BYTES
MAX_SEQUENCE = 65535


class ProtocolError(ValueError):
    """Raised for framing, CRC, schema, or range violations."""


@dataclass(frozen=True)
class Frame:
    kind: str
    sequence: int
    fields: Tuple[str, ...]


def crc16_ccitt_false(data: bytes) -> int:
    """Return CRC-16/CCITT-FALSE (poly 0x1021, init 0xffff)."""

    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def _parse_int(value: str, label: str, minimum: int, maximum: int) -> int:
    if not value or value.strip() != value:
        raise ProtocolError("{} is not a canonical integer".format(label))
    try:
        parsed = int(value, 10)
    except ValueError as exc:
        raise ProtocolError("{} is not an integer".format(label)) from exc
    if str(parsed) != value:
        raise ProtocolError("{} is not a canonical integer".format(label))
    if parsed < minimum or parsed > maximum:
        raise ProtocolError("{} outside [{}, {}]".format(label, minimum, maximum))
    return parsed


def _validate_schema(frame: Frame) -> None:
    schemas: Mapping[str, Sequence[Tuple[str, int, int]]] = {
        "CMD": (
            ("linear_mm_s", -450, 450),
            ("angular_mrad_s", -1800, 1800),
        ),
        "PING": (),
        "ESTOP": (("engaged", 0, 1),),
        "ODOM": (
            ("left_ticks", -(2**31), 2**31 - 1),
            ("right_ticks", -(2**31), 2**31 - 1),
            ("left_mrad_s", -100000, 100000),
            ("right_mrad_s", -100000, 100000),
            ("battery_mv", 0, 20000),
            ("flags", 0, 65535),
        ),
        "IMU": (
            ("ax_mg", -16000, 16000),
            ("ay_mg", -16000, 16000),
            ("az_mg", -16000, 16000),
            ("gx_mdps", -2000000, 2000000),
            ("gy_mdps", -2000000, 2000000),
            ("gz_mdps", -2000000, 2000000),
        ),
        "RANGE": (("front_mm", 0, 2000),),
        "PONG": (),
    }
    if frame.kind == "BOOT":
        if len(frame.fields) != 2:
            raise ProtocolError("BOOT expects product and protocol version")
        product, version = frame.fields
        if product != "WILDEBEEST_BASE":
            raise ProtocolError("unsupported BOOT product")
        _parse_int(version, "protocol_version", 1, 65535)
        return
    if frame.kind == "ERR":
        if len(frame.fields) != 1 or frame.fields[0] not in {"TYPE", "SCHEMA", "RANGE"}:
            raise ProtocolError("invalid ERR code")
        return
    if frame.kind not in schemas:
        raise ProtocolError("unknown frame type: {}".format(frame.kind))
    schema = schemas[frame.kind]
    if len(frame.fields) != len(schema):
        raise ProtocolError(
            "{} expects {} fields, received {}".format(
                frame.kind, len(schema), len(frame.fields)
            )
        )
    _parse_int(str(frame.sequence), "sequence", 0, MAX_SEQUENCE)
    for value, (label, minimum, maximum) in zip(frame.fields, schema):
        _parse_int(value, label, minimum, maximum)


def encode_frame(kind: str, sequence: int, *fields: Union[str, int]) -> bytes:
    """Validate and encode one newline-terminated frame."""

    if not kind or not kind.isascii() or kind.upper() != kind or not kind.isalpha():
        raise ProtocolError("frame type must contain uppercase ASCII letters")
    if isinstance(sequence, bool) or not isinstance(sequence, int):
        raise ProtocolError("sequence must be an integer")
    frame = Frame(kind, sequence, tuple(str(field) for field in fields))
    _validate_schema(frame)
    payload = ",".join((kind, str(frame.sequence)) + frame.fields).encode("ascii")
    checksum = crc16_ccitt_false(payload)
    encoded = b"@" + payload + b"*" + ("{:04X}".format(checksum)).encode("ascii") + b"\n"
    if len(encoded) > MAX_FRAME_BYTES:
        raise ProtocolError("encoded frame exceeds maximum line length")
    return encoded


def decode_frame(raw: Union[bytes, str]) -> Frame:
    """Decode one complete line and reject malformed or unsafe values."""

    if isinstance(raw, str):
        try:
            data = raw.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ProtocolError("frame is not ASCII") from exc
    else:
        data = bytes(raw)
    if len(data) > MAX_FRAME_BYTES:
        raise ProtocolError("frame exceeds maximum line length")
    data = data.rstrip(b"\r\n")
    if b"\r" in data or b"\n" in data:
        raise ProtocolError("embedded newline")
    if not data.startswith(b"@"):
        raise ProtocolError("missing start marker")
    if data.count(b"*") != 1:
        raise ProtocolError("frame must contain one checksum marker")
    payload, checksum_text = data[1:].split(b"*", 1)
    if len(checksum_text) != 4:
        raise ProtocolError("checksum must contain four hexadecimal digits")
    if any(byte not in b"0123456789abcdefABCDEF" for byte in checksum_text):
        raise ProtocolError("checksum must contain hexadecimal digits only")
    try:
        expected = int(checksum_text, 16)
        text = payload.decode("ascii")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProtocolError("invalid ASCII or checksum") from exc
    actual = crc16_ccitt_false(payload)
    if actual != expected:
        raise ProtocolError(
            "CRC mismatch: received {:04X}, calculated {:04X}".format(expected, actual)
        )
    parts = text.split(",")
    if len(parts) < 2:
        raise ProtocolError("frame is missing type or sequence")
    kind = parts[0]
    if not kind or kind.upper() != kind or not kind.isalpha():
        raise ProtocolError("invalid frame type")
    sequence = _parse_int(parts[1], "sequence", 0, MAX_SEQUENCE)
    frame = Frame(kind, sequence, tuple(parts[2:]))
    _validate_schema(frame)
    return frame


class FrameStreamDecoder:
    """Bounded newline decoder that resynchronizes after noise or overflow."""

    def __init__(self, maximum_line_bytes: int = MAX_FRAME_BYTES):
        if maximum_line_bytes < 16:
            raise ValueError("maximum_line_bytes is too small")
        self.maximum_line_bytes = maximum_line_bytes
        self._buffer = bytearray()
        self.dropped_lines = 0

    def feed(self, chunk: bytes) -> List[bytes]:
        lines: List[bytes] = []
        for byte in bytes(chunk):
            if byte == ord("@"):
                if self._buffer:
                    self.dropped_lines += 1
                self._buffer.clear()
                self._buffer.append(byte)
                continue
            if byte == 10:
                if self._buffer:
                    lines.append(bytes(self._buffer) + b"\n")
                self._buffer.clear()
                continue
            if len(self._buffer) >= self.maximum_line_bytes - 1:
                self._buffer.clear()
                self.dropped_lines += 1
                continue
            if not self._buffer:
                continue
            self._buffer.append(byte)
        return lines
