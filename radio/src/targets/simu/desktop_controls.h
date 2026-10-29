/* Native DevEBox simulator controls. No hardware power/ADC code belongs here. */
#pragma once

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstring>

#if defined(RADIO_SAOLALINKV1) && defined(SAOLALINK_DEVEBOX) && !defined(__wasm__) && !defined(__EMSCRIPTEN__)
#define TYVOR_DESKTOP_CONTROLS
#endif

struct DesktopPowerHold {
  static constexpr uint32_t holdTicks = 200; // 2 seconds, simulator-only
  std::atomic<bool> enabled{false};
  std::atomic<bool> pressed{false};
  std::atomic<bool> boardOff{false};
  std::atomic<uint32_t> progress{0};
  // Only the firmware menu task touches the debounce/hold state.
  bool holding = false;
  uint32_t started = 0;

  enum Result { On, Press, Off };
  Result poll(uint32_t now)
  {
    if (!enabled.load() || !pressed.load()) {
      holding = false;
      progress.store(0);
      return On;
    }
    if (!holding) {
      holding = true;
      started = now;
    }
    uint32_t elapsed = now - started;
    progress.store(std::min(elapsed, holdTicks));
    return elapsed >= holdTicks ? Off : Press;
  }
};

#if defined(TYVOR_DESKTOP_CONTROLS)
inline DesktopPowerHold desktopPower;
#endif

inline bool desktopThrottleOnLeft(unsigned mode) { return (mode & 1U) != 0; }

// The HAL exports normalized main inputs named LH/LV/RV/RH, not mixer channels.
// Y=0 is the top of the on-screen gimbal; pushing up increases normalized ADC.
inline bool desktopMainAxis(const char* name, float lx, float ly,
                            float rx, float ry, uint16_t& value)
{
  float position;
  if (!std::strcmp(name, "LH")) position = lx;
  else if (!std::strcmp(name, "LV")) position = 1.0f - ly;
  else if (!std::strcmp(name, "RV")) position = 1.0f - ry;
  else if (!std::strcmp(name, "RH")) position = rx;
  else return false;
  value = uint16_t(std::clamp(position, 0.0f, 1.0f) * 4096.0f);
  return true;
}
