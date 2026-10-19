#pragma once

#include <stdint.h>

// Ignore the press that supplied initial power. Arm only after a stable release.
// Used by the power driver, independently of the CLI reporting filter.
class DeveboxPowerButton {
 public:
  void reset() { initialized = armed = false; }

  bool update(bool rawPressed, uint32_t now) {
    if (!initialized) {
      initialized = true;
      candidate = stable = rawPressed;
      since = now;
    }
    if (rawPressed != candidate) {
      candidate = rawPressed;
      since = now;
    }
    if (uint32_t(now - since) >= 30) {
      stable = candidate;
      if (!stable) armed = true;
    }
    return armed && stable;
  }

 private:
  bool initialized = false, armed = false, candidate = false, stable = false;
  uint32_t since = 0;
};
