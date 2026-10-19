#pragma once

#include <stdint.h>

// CLI-only reporting filter; does not change ADC acquisition or mixer values.
class DeveboxGimbalMonitor {
 public:
  static constexpr unsigned count = 4;
  static constexpr uint16_t threshold = 16; // 12-bit ADC counts, cumulative
  static constexpr uint32_t intervalMs = 50;

  void reset(const uint16_t* values, uint32_t now) {
    for (unsigned i = 0; i < count; ++i) last[i] = values[i];
    sampledAt = now;
  }

  uint32_t update(const uint16_t* values, uint32_t now) {
    if (uint32_t(now - sampledAt) < intervalMs) return 0;
    sampledAt = now;
    uint32_t changed = 0;
    for (unsigned i = 0; i < count; ++i) {
      int diff = int(values[i]) - int(last[i]);
      if (diff >= threshold || diff <= -int(threshold)) changed |= 1U << i;
    }
    return changed;
  }

  int delta(unsigned i, uint16_t value) const { return int(value) - int(last[i]); }
  void reported(unsigned i, uint16_t value) { last[i] = value; }

 private:
  uint16_t last[count] = {};
  uint32_t sampledAt = 0;
};
