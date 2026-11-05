#pragma once
#include <stdint.h>

// Each input must stay unchanged for 30 ms. Independent timers preserve
// simultaneous presses/releases; unsigned subtraction handles timer wrap.
class DeveboxButtonMonitor {
 public:
  void reset(uint32_t raw, uint32_t now) {
    candidate = stable = raw;
    for (auto& t : since) t = now;
  }
  uint32_t update(uint32_t raw, uint32_t now) {
    uint32_t changed = 0;
    for (unsigned i = 0; i < 7; ++i) {
      uint32_t bit = 1U << i;
      if ((raw ^ candidate) & bit) {
        candidate ^= bit;
        since[i] = now;
      }
      if (((candidate ^ stable) & bit) && uint32_t(now - since[i]) >= 30) {
        stable ^= bit;
        changed |= bit;
      }
    }
    return changed;
  }
  uint32_t value() const { return stable; }
 private:
  uint32_t candidate = 0, stable = 0;
  uint32_t since[7] = {};
};
