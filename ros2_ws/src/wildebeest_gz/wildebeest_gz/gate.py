"""Clock-independent motion watchdog used in simulation."""

from dataclasses import dataclass
import math
from typing import Optional, Tuple


@dataclass
class SafetyTwistGate:
    """Fail closed on stale commands, estop, invalid data, or time reversal."""

    timeout_s: float = 0.25
    max_linear_m_s: float = 0.45
    max_angular_rad_s: float = 1.8

    def __post_init__(self) -> None:
        values = (
            self.timeout_s,
            self.max_linear_m_s,
            self.max_angular_rad_s,
        )
        if not all(math.isfinite(value) and value > 0.0 for value in values):
            raise ValueError('timeout and command limits must be finite and positive')
        self.estopped = False
        self._command: Tuple[float, float] = (0.0, 0.0)
        self._received_s: Optional[float] = None

    def receive(self, linear: float, angular: float, now_s: float) -> bool:
        """Accept a fresh command, returning false when it is unsafe."""

        if not all(math.isfinite(value) for value in (linear, angular, now_s)):
            self.invalidate()
            return False
        if self.estopped:
            self.invalidate()
            return False
        self._command = (
            max(-self.max_linear_m_s, min(self.max_linear_m_s, linear)),
            max(-self.max_angular_rad_s, min(self.max_angular_rad_s, angular)),
        )
        self._received_s = now_s
        return True

    def set_estop(self, engaged: bool) -> None:
        """Update estop state; either edge invalidates the old command."""

        if engaged or self.estopped != engaged:
            self.invalidate()
        self.estopped = engaged

    def output(self, now_s: float) -> Tuple[float, float]:
        """Return a safe command for the current monotonic time."""

        if not math.isfinite(now_s) or self.estopped or self._received_s is None:
            return 0.0, 0.0
        age = now_s - self._received_s
        if age < 0.0 or age > self.timeout_s:
            self.invalidate()
            return 0.0, 0.0
        return self._command

    def invalidate(self) -> None:
        """Forget the previous command so it cannot be replayed."""

        self._command = (0.0, 0.0)
        self._received_s = None
