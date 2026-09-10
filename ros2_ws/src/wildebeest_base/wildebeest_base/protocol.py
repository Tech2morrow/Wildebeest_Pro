"""Framing and validation for the Wildebeest Arduino serial protocol.

Wire format::

    @TYPE,seq,field...*CRC16\n

The four hexadecimal CRC characters encode CRC-16/CCITT-FALSE over the ASCII
bytes between ``@`` and ``*``.  Parsing is deliberately strict: malformed,
oversized, non-ASCII, out-of-range, and checksum-invalid messages never reach
the motion or odometry code.
"""

from dataclasses import dataclass
import math
import re
from typing import Iterable, List, Tuple, Union


PROTOCOL_VERSION = 1
CONTROLLER_IDENTITY = 'WILDEBEEST_BASE'
MAX_FRAME_BYTES = 128
MAX_SEQUENCE = 0xFFFF
_TYPE_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]{0,15}$')


class ProtocolError(ValueError):
    """Raised when a frame does not satisfy the wire contract."""


@dataclass(frozen=True)
class Frame:
    """A checksum-verified protocol frame."""

    kind: str
    sequence: int
    fields: Tuple[str, ...] = ()


@dataclass(frozen=True)
class OdomTelemetry:
    sequence: int
    left_ticks: int
    right_ticks: int
    left_rad_s: float
    right_rad_s: float
    battery_v: float
    flags: int


@dataclass(frozen=True)
class ImuTelemetry:
    sequence: int
    acceleration_m_s2: Tuple[float, float, float]
    angular_velocity_rad_s: Tuple[float, float, float]


@dataclass(frozen=True)
class RangeTelemetry:
    sequence: int
    front_m: float


Telemetry = Union[OdomTelemetry, ImuTelemetry, RangeTelemetry, Frame]


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


def _validate_sequence(sequence: int) -> None:
    if isinstance(sequence, bool) or not 0 <= sequence <= MAX_SEQUENCE:
        raise ProtocolError(f'sequence must be in [0, {MAX_SEQUENCE}]')


def encode_frame(kind: str, sequence: int, fields: Iterable[object] = ()) -> bytes:
    """Encode one complete frame, including checksum and newline."""

    _validate_sequence(sequence)
    if not _TYPE_PATTERN.fullmatch(kind):
        raise ProtocolError(f'invalid message type: {kind!r}')
    tokens = [kind, str(sequence)]
    for field in fields:
        text = str(field)
        if not text or any(char in text for char in ',*@\r\n'):
            raise ProtocolError(f'invalid field: {text!r}')
        try:
            text.encode('ascii')
        except UnicodeEncodeError as exc:
            raise ProtocolError('fields must contain ASCII only') from exc
        tokens.append(text)
    body = ','.join(tokens).encode('ascii')
    frame = b'@' + body + b'*' + f'{crc16_ccitt_false(body):04X}'.encode() + b'\n'
    if len(frame) > MAX_FRAME_BYTES:
        raise ProtocolError('encoded frame exceeds maximum length')
    return frame


def decode_frame(raw: bytes) -> Frame:
    """Decode and verify one newline-terminated (or stripped) frame."""

    if not isinstance(raw, bytes):
        raise ProtocolError('frame must be bytes')
    if not raw or len(raw) > MAX_FRAME_BYTES:
        raise ProtocolError('empty or oversized frame')
    raw = raw.rstrip(b'\r\n')
    if not raw:
        raise ProtocolError('empty or oversized frame')
    if not raw.startswith(b'@'):
        raise ProtocolError('missing start marker')
    if raw.count(b'*') != 1:
        raise ProtocolError('frame must contain one checksum separator')
    body, checksum = raw[1:].split(b'*', 1)
    if len(checksum) != 4:
        raise ProtocolError('checksum must contain four hexadecimal characters')
    try:
        expected = int(checksum, 16)
        body_text = body.decode('ascii')
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProtocolError('invalid checksum or non-ASCII body') from exc
    actual = crc16_ccitt_false(body)
    if expected != actual:
        raise ProtocolError(
            f'checksum mismatch: received {expected:04X}, calculated {actual:04X}'
        )
    tokens = body_text.split(',')
    if len(tokens) < 2 or any(token == '' for token in tokens):
        raise ProtocolError('message type, sequence, and fields may not be empty')
    kind = tokens[0]
    if not _TYPE_PATTERN.fullmatch(kind):
        raise ProtocolError(f'invalid message type: {kind!r}')
    sequence = _parse_int(tokens[1], 'sequence', 0, MAX_SEQUENCE)
    return Frame(kind=kind, sequence=sequence, fields=tuple(tokens[2:]))


class FrameStreamDecoder:
    """Incrementally split a byte stream while bounding retained memory."""

    def __init__(self, max_frame_bytes: int = MAX_FRAME_BYTES) -> None:
        if max_frame_bytes < 16:
            raise ValueError('max_frame_bytes is too small')
        self._maximum = max_frame_bytes
        self._buffer = bytearray()

    def feed(self, data: bytes) -> Tuple[List[Frame], List[str]]:
        """Consume bytes and return ``(valid_frames, rejection_reasons)``."""

        if not isinstance(data, bytes):
            raise TypeError('stream data must be bytes')
        self._buffer.extend(data)
        frames: List[Frame] = []
        errors: List[str] = []

        while b'\n' in self._buffer:
            line, _, remainder = self._buffer.partition(b'\n')
            self._buffer = bytearray(remainder)
            start = line.rfind(b'@')
            if start < 0:
                if line.strip(b'\r'):
                    errors.append('discarded bytes without a start marker')
                continue
            if start:
                errors.append('discarded bytes before a start marker')
            candidate = bytes(line[start:]) + b'\n'
            try:
                frames.append(decode_frame(candidate))
            except ProtocolError as exc:
                errors.append(str(exc))

        if len(self._buffer) > self._maximum:
            start = self._buffer.rfind(b'@')
            if start >= 0 and len(self._buffer) - start <= self._maximum:
                self._buffer = self._buffer[start:]
            else:
                self._buffer.clear()
            errors.append('unterminated frame exceeded maximum length')
        return frames, errors

    def clear(self) -> None:
        self._buffer.clear()


def encode_cmd(sequence: int, linear_m_s: float, angular_rad_s: float) -> bytes:
    """Encode a body velocity command using integer millimetre units."""

    _require_finite(linear_m_s, 'linear_m_s')
    _require_finite(angular_rad_s, 'angular_rad_s')
    linear_mm_s = round(linear_m_s * 1000.0)
    angular_mrad_s = round(angular_rad_s * 1000.0)
    if not -450 <= linear_mm_s <= 450:
        raise ProtocolError('linear command exceeds protocol bounds')
    if not -1800 <= angular_mrad_s <= 1800:
        raise ProtocolError('angular command exceeds protocol bounds')
    return encode_frame('CMD', sequence, (linear_mm_s, angular_mrad_s))


def encode_ping(sequence: int) -> bytes:
    return encode_frame('PING', sequence)


def encode_estop(sequence: int, engaged: bool) -> bytes:
    if not isinstance(engaged, bool):
        raise ProtocolError('engaged must be a bool')
    return encode_frame('ESTOP', sequence, (int(engaged),))


def validate_schema(frame: Frame) -> Frame:
    """Validate field counts and integer ranges for any protocol-v1 message."""

    field_counts = {
        'CMD': 2,
        'PING': 0,
        'ESTOP': 1,
        'ODOM': 6,
        'IMU': 6,
        'RANGE': 1,
        'PONG': 0,
        'BOOT': 2,
        'ERR': 1,
    }
    if frame.kind not in field_counts:
        raise ProtocolError(f'unknown frame type: {frame.kind}')
    _require_field_count(frame, field_counts[frame.kind])
    if frame.kind == 'CMD':
        _parse_int(frame.fields[0], 'linear_mm_s', -450, 450)
        _parse_int(frame.fields[1], 'angular_mrad_s', -1800, 1800)
    elif frame.kind == 'ESTOP':
        _parse_int(frame.fields[0], 'estop', 0, 1)
    elif frame.kind == 'ODOM':
        _parse_int(frame.fields[0], 'left_ticks', -2147483648, 2147483647)
        _parse_int(frame.fields[1], 'right_ticks', -2147483648, 2147483647)
        _parse_int(frame.fields[2], 'left_mrad_s', -100000, 100000)
        _parse_int(frame.fields[3], 'right_mrad_s', -100000, 100000)
        _parse_int(frame.fields[4], 'battery_mv', 0, 20000)
        _parse_int(frame.fields[5], 'flags', 0, 65535)
    elif frame.kind == 'IMU':
        for index, axis in enumerate('xyz'):
            _parse_int(frame.fields[index], f'acceleration_{axis}_mg', -16000, 16000)
        for index, axis in enumerate('xyz', start=3):
            _parse_int(frame.fields[index], f'gyro_{axis}_mdps', -2000000, 2000000)
    elif frame.kind == 'RANGE':
        _parse_int(frame.fields[0], 'front_mm', 0, 2000)
    return frame


def validate_controller_boot(frame: Frame) -> Frame:
    """Require the exact controller identity and protocol version."""

    validate_schema(frame)
    if frame.kind != 'BOOT':
        raise ProtocolError('controller readiness requires a BOOT frame')
    if frame.sequence != 0:
        raise ProtocolError('BOOT sequence must be zero')
    if frame.fields != (CONTROLLER_IDENTITY, str(PROTOCOL_VERSION)):
        raise ProtocolError(
            'incompatible controller identity/version: ' + ','.join(frame.fields)
        )
    return frame


def parse_telemetry(frame: Frame) -> Telemetry:
    """Validate and convert a telemetry frame to SI units."""

    validate_schema(frame)
    if frame.kind == 'ODOM':
        return OdomTelemetry(
            sequence=frame.sequence,
            left_ticks=_parse_int(frame.fields[0], 'left_ticks', -2147483648, 2147483647),
            right_ticks=_parse_int(frame.fields[1], 'right_ticks', -2147483648, 2147483647),
            left_rad_s=_parse_int(frame.fields[2], 'left_mrad_s', -100000, 100000) / 1000.0,
            right_rad_s=_parse_int(frame.fields[3], 'right_mrad_s', -100000, 100000) / 1000.0,
            battery_v=_parse_int(frame.fields[4], 'battery_mv', 0, 20000) / 1000.0,
            flags=_parse_int(frame.fields[5], 'flags', 0, 65535),
        )
    if frame.kind == 'IMU':
        acceleration = tuple(
            _parse_int(value, f'acceleration_{axis}_mg', -16000, 16000) * 9.80665 / 1000.0
            for axis, value in zip('xyz', frame.fields[:3])
        )
        angular = tuple(
            _parse_int(value, f'gyro_{axis}_mdps', -2000000, 2000000)
            * math.pi / 180000.0
            for axis, value in zip('xyz', frame.fields[3:])
        )
        return ImuTelemetry(frame.sequence, acceleration, angular)
    if frame.kind == 'RANGE':
        millimetres = _parse_int(frame.fields[0], 'front_mm', 0, 2000)
        return RangeTelemetry(frame.sequence, millimetres / 1000.0)
    if frame.kind == 'PONG':
        return frame
    if frame.kind == 'BOOT':
        return frame
    if frame.kind == 'ERR':
        return frame
    raise ProtocolError(f'unknown telemetry type: {frame.kind}')


def _require_field_count(frame: Frame, expected: int) -> None:
    if len(frame.fields) != expected:
        raise ProtocolError(
            f'{frame.kind} expects {expected} fields, received {len(frame.fields)}'
        )


def _parse_int(text: str, name: str, minimum: int, maximum: int) -> int:
    if not re.fullmatch(r'-?(0|[1-9][0-9]*)', text):
        raise ProtocolError(f'{name} must be a canonical base-10 integer')
    value = int(text)
    if not minimum <= value <= maximum:
        raise ProtocolError(f'{name} must be in [{minimum}, {maximum}]')
    return value


def _require_finite(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ProtocolError(f'{name} must be finite')
