"""ROS-independent command freshness checks for the motion interlock."""

import math
from typing import Optional


def motion_command_is_ready(
    now: float,
    command_time: float,
    motion_ready_after: Optional[float],
    timeout_s: float,
    controller_ready: bool,
) -> bool:
    """Return true only for a fresh command accepted after the last interlock.

    ``motion_ready_after`` is ``None`` until a controller handshake is seen.
    Strictly greater-than ordering ensures a command captured at or before an
    E-stop release can never be replayed when motion becomes available.
    """

    if not controller_ready:
        return False
    values = (float(now), float(command_time), float(timeout_s))
    if not all(math.isfinite(value) for value in values) or timeout_s <= 0.0:
        return False
    if motion_ready_after is None or not math.isfinite(float(motion_ready_after)):
        return False
    age = now - command_time
    return command_time > float(motion_ready_after) and 0.0 <= age <= timeout_s


def controller_boot_is_supported(sequence: int, identity: str, version: str) -> bool:
    """Recognize the one controller handshake supported by protocol v1."""

    return sequence == 0 and identity == "WILDEBEEST_BASE" and version == "1"
