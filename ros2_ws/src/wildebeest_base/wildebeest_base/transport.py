"""Transport abstractions for physical and deterministic mock controllers."""

from abc import ABC, abstractmethod
import threading
import time
from typing import Optional

from .mock_controller import MockController
from .protocol import FrameStreamDecoder, ProtocolError


class TransportError(RuntimeError):
    """A recoverable controller transport failure."""


class Transport(ABC):
    @property
    @abstractmethod
    def is_open(self) -> bool:
        pass

    @abstractmethod
    def open(self) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def read(self, maximum_bytes: int = 4096) -> bytes:
        pass

    @abstractmethod
    def write(self, data: bytes) -> None:
        pass


class PySerialTransport(Transport):
    """Non-blocking pyserial transport with bounded writes."""

    def __init__(self, port: str, baudrate: int, write_timeout_s: float = 0.1) -> None:
        self.port = port
        self.baudrate = baudrate
        self.write_timeout_s = write_timeout_s
        self._serial = None
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        return bool(self._serial is not None and self._serial.is_open)

    def open(self) -> None:
        try:
            import serial

            connection = serial.serial_for_url(
                self.port,
                baudrate=self.baudrate,
                timeout=0.0,
                write_timeout=self.write_timeout_s,
            )
            self._serial = connection
        except Exception as exc:
            self._serial = None
            raise TransportError(f'cannot open {self.port}: {exc}') from exc

    def close(self) -> None:
        connection, self._serial = self._serial, None
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    def read(self, maximum_bytes: int = 4096) -> bytes:
        connection = self._serial
        if connection is None:
            raise TransportError('serial port is closed')
        try:
            waiting = min(maximum_bytes, max(1, connection.in_waiting))
            return connection.read(waiting)
        except Exception as exc:
            self.close()
            raise TransportError(f'serial read failed: {exc}') from exc

    def write(self, data: bytes) -> None:
        connection = self._serial
        if connection is None:
            raise TransportError('serial port is closed')
        try:
            with self._lock:
                written = connection.write(data)
            if written != len(data):
                raise TransportError(f'short serial write: {written}/{len(data)} bytes')
        except TransportError:
            raise
        except Exception as exc:
            self.close()
            raise TransportError(f'serial write failed: {exc}') from exc


class MockTransport(Transport):
    """In-process Arduino replacement with the exact production protocol."""

    def __init__(self, controller: Optional[MockController] = None) -> None:
        self.controller = controller or MockController()
        self._decoder = FrameStreamDecoder()
        self._open = False
        self._last_update_s = 0.0
        self._read_buffer = bytearray()
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        return self._open

    def open(self) -> None:
        with self._lock:
            self._open = True
            self._last_update_s = time.monotonic()
            self._decoder.clear()
            self._read_buffer.clear()
            self.controller.drain()
            self.controller.boot()

    def close(self) -> None:
        with self._lock:
            self._open = False

    def read(self, maximum_bytes: int = 4096) -> bytes:
        with self._lock:
            self._ensure_open()
            now = time.monotonic()
            self.controller.advance(min(0.25, max(0.0, now - self._last_update_s)))
            self._last_update_s = now
            self._read_buffer.extend(self.controller.drain())
            result = bytes(self._read_buffer[:maximum_bytes])
            del self._read_buffer[:maximum_bytes]
            return result

    def write(self, data: bytes) -> None:
        with self._lock:
            self._ensure_open()
            frames, errors = self._decoder.feed(data)
            if errors:
                raise TransportError('mock rejected command: ' + '; '.join(errors))
            try:
                for frame in frames:
                    self.controller.handle_frame(frame)
            except ProtocolError as exc:
                raise TransportError(f'mock rejected command: {exc}') from exc

    def _ensure_open(self) -> None:
        if not self._open:
            raise TransportError('mock transport is closed')
