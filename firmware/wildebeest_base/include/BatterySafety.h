#pragma once

#include <stdint.h>

namespace wb {

// Return the next hysteretic cutoff state. A zero sample means "not measured"
// and preserves the current state rather than silently authorizing motion.
inline bool nextLowVoltageMotorStop(bool active, uint16_t batteryMv,
                                    uint16_t stopMv, uint16_t hysteresisMv) {
  if (batteryMv == 0U) return active;
  const uint32_t releaseMv =
      static_cast<uint32_t>(stopMv) + static_cast<uint32_t>(hysteresisMv);
  if (active) return static_cast<uint32_t>(batteryMv) < releaseMv;
  return batteryMv <= stopMv;
}

}  // namespace wb
