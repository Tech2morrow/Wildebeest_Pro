#pragma once

#include <Arduino.h>
#include <stdlib.h>
#include <string.h>

namespace wb {

// Complete protocol-v1 frames are limited to 128 wire bytes including '\n'.
// The receiver stores the preceding bytes and reserves one byte for '\0'.
constexpr size_t MAX_FRAME_BYTES = 128;
constexpr size_t RX_FRAME_CAPACITY = MAX_FRAME_BYTES;

inline uint16_t crc16CcittFalse(const uint8_t* data, size_t length) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < length; ++i) {
    crc ^= static_cast<uint16_t>(data[i]) << 8;
    for (uint8_t bit = 0; bit < 8; ++bit) {
      crc = (crc & 0x8000U) ? static_cast<uint16_t>((crc << 1) ^ 0x1021U)
                            : static_cast<uint16_t>(crc << 1);
    }
  }
  return crc;
}

inline bool parseLongStrict(const char* text, long minimum, long maximum, long& value) {
  if (text == nullptr || *text == '\0') return false;
  const char* cursor = text;
  if (*cursor == '-') ++cursor;
  if (*cursor == '\0') return false;
  if (*cursor == '0' && cursor[1] != '\0') return false;
  for (const char* digit = cursor; *digit != '\0'; ++digit) {
    if (*digit < '0' || *digit > '9') return false;
  }
  char* end = nullptr;
  const long parsed = strtol(text, &end, 10);
  if (*end != '\0' || parsed < minimum || parsed > maximum) return false;
  value = parsed;
  return true;
}

class LineReceiver {
 public:
  LineReceiver() : length_(0), overflow_(false), ready_(false) { buffer_[0] = '\0'; }

  void push(char byte) {
    if (byte == '@') {
      length_ = 0;
      overflow_ = false;
      ready_ = false;
      buffer_[length_++] = byte;
      return;
    }
    if (length_ == 0) return;
    if (byte == '\r') return;
    if (byte == '\n') {
      if (!overflow_) {
        buffer_[length_] = '\0';
        ready_ = true;
      } else {
        reset();
      }
      return;
    }
    if (length_ + 1 >= RX_FRAME_CAPACITY) {
      overflow_ = true;
      return;
    }
    buffer_[length_++] = byte;
  }

  bool ready() const { return ready_; }
  char* data() { return buffer_; }
  bool overflowed() const { return overflow_; }
  void consume() { reset(); }

 private:
  void reset() {
    length_ = 0;
    overflow_ = false;
    ready_ = false;
    buffer_[0] = '\0';
  }

  char buffer_[RX_FRAME_CAPACITY];
  size_t length_;
  bool overflow_;
  bool ready_;
};

// Validates in place and returns a pointer to the comma-separated body.
inline char* validateFrame(char* frame) {
  if (frame == nullptr || frame[0] != '@') return nullptr;
  char* star = strrchr(frame, '*');
  if (star == nullptr || strlen(star + 1) != 4) return nullptr;
  for (const char* digit = star + 1; *digit != '\0'; ++digit) {
    const bool decimal = *digit >= '0' && *digit <= '9';
    const bool upper = *digit >= 'A' && *digit <= 'F';
    const bool lower = *digit >= 'a' && *digit <= 'f';
    if (!decimal && !upper && !lower) return nullptr;
  }
  char* crcEnd = nullptr;
  const unsigned long expected = strtoul(star + 1, &crcEnd, 16);
  if (crcEnd == nullptr || *crcEnd != '\0' || expected > 0xFFFFUL) return nullptr;
  const char* body = frame + 1;
  const size_t bodyLength = static_cast<size_t>(star - body);
  const uint16_t actual = crc16CcittFalse(reinterpret_cast<const uint8_t*>(body), bodyLength);
  if (actual != static_cast<uint16_t>(expected)) return nullptr;
  *star = '\0';
  return frame + 1;
}

inline void writeFrame(Stream& output, const char* body) {
  const uint16_t crc = crc16CcittFalse(reinterpret_cast<const uint8_t*>(body), strlen(body));
  output.print('@');
  output.print(body);
  output.print('*');
  if (crc < 0x1000U) output.print('0');
  if (crc < 0x0100U) output.print('0');
  if (crc < 0x0010U) output.print('0');
  output.println(crc, HEX);
}

}  // namespace wb
