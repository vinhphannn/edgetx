#pragma once

#if defined(SAOLALINK_DEVEBOX_V2) && !defined(SIMU)
#include <stdint.h>
// Literal/localized messages remain valid while the startup prompt is active.
// Exposed through `devboard` before the menus task reaches perMain().
extern const char* volatile deveboxStartupStatus;

struct DeveboxStartupTiming {
  uint32_t rtcMs;
  uint32_t firstDisplayAtMs;
  uint32_t sdMountMs;
  uint32_t sdFreeMs;
  uint32_t radioMs;
  uint32_t modelMs;
  uint32_t progressFrames;
  uint32_t displayMs;
};
extern DeveboxStartupTiming deveboxStartupTiming;
void deveboxStartupDisplayProgress();
void deveboxStartupDisplayStop();
#endif
