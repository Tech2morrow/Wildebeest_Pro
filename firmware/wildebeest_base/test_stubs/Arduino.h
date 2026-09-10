#pragma once

#include <stddef.h>
#include <stdint.h>

#define HEX 16
#define HIGH 1
#define A0 14
#define A1 15
#define A2 16

class Stream {
 public:
  template <typename T>
  size_t print(const T&) { return 0; }

  template <typename T>
  size_t print(const T&, int) { return 0; }

  template <typename T>
  size_t println(const T&) { return 0; }

  template <typename T>
  size_t println(const T&, int) { return 0; }
};
