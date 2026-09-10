"""Hardware-independent core utilities for the Wildebeest Pro ROS 1 base."""

from .odometry import DifferentialOdometry, DriveGeometry, OdometryDiscontinuity, OdometrySample
from .protocol import Frame, ProtocolError, crc16_ccitt_false, decode_frame, encode_frame

__all__ = [
    "DifferentialOdometry",
    "DriveGeometry",
    "Frame",
    "OdometrySample",
    "OdometryDiscontinuity",
    "ProtocolError",
    "crc16_ccitt_false",
    "decode_frame",
    "encode_frame",
]
