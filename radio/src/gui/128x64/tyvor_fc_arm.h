/* Version-scoped FC telemetry presentation. Never a control/arming source. */
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <initializer_list>
#include "tyvor_flight_data.h"

enum class TyvorFcArmProfile : uint8_t { Unconfigured, Betaflight455 };

// Betaflight tag 4.5.5, src/main/telemetry/crsf.c:348-382.
// This release appends only '*'. Later '!'/'?' dialects require another profile.
inline TyvorArmState tyvorDecodeFcArm(TyvorFcArmProfile profile,
                                     const char* text, size_t capacity)
{
  if (profile != TyvorFcArmProfile::Betaflight455 || !text) return TyvorArmState::Unknown;
  size_t length = 0;
  while (length < capacity && text[length]) ++length;
  if (!length || length == capacity) return TyvorArmState::Unknown;
  const bool disarmed = text[length - 1] == '*';
  const size_t baseLength = length - unsigned(disarmed);
  // Failsafe strings are deliberately UNKNOWN, with or without a suffix.
  // WAIT is emitted only in a disarmed GPS branch, so bare WAIT is invalid.
  if (disarmed && baseLength == 4 && !memcmp(text, "WAIT", 4)) return TyvorArmState::Disarmed;
  for (const char* mode : {"ACRO", "RTH", "MANU", "STAB", "HOR", "AIR"}) {
    if (strlen(mode) == baseLength && !memcmp(text, mode, baseLength))
      return disarmed ? TyvorArmState::Disarmed : TyvorArmState::Armed;
  }
  return TyvorArmState::Unknown;
}

struct TyvorFcArmConfig {
  TyvorFcArmProfile profile = TyvorFcArmProfile::Unconfigured;
  uint8_t sensor = 0;  // 1-based; sensor identity must be CRSF 0x21/0/0 text.
  uint16_t modules = 0;
  bool verified = false;
};

inline bool tyvorDecodeFcArmConfig(const char* text, TyvorFcArmConfig& out)
{
  if (!text) return false;
  uint16_t values[5];
  for (unsigned i = 0; i < 5; ++i) {
    if (*text < '0' || *text > '9') return false;
    uint32_t value = 0;
    do {
      value = value * 10 + (*text++ - '0');
      if (value > 65535) return false;
    } while (*text >= '0' && *text <= '9');
    values[i] = value;
    if (i < 4) { if (*text++ != ',') return false; }
    else if (*text) return false;
  }
  if (values[0] != 1 || values[1] > 1 || values[2] > 255 || values[4] > 1) return false;
  out.profile = TyvorFcArmProfile(values[1]); out.sensor = values[2];
  out.modules = values[3]; out.verified = values[4];
  return true;
}

inline void tyvorEncodeFcArmConfig(char (&text)[40], const TyvorFcArmConfig& c)
{
  snprintf(text, sizeof(text), "1,%u,%u,%u,%u", unsigned(c.profile),
           unsigned(c.sensor), unsigned(c.modules), unsigned(c.verified));
}

#if defined(RADIO_SAOLALINKV1) && defined(SAOLALINK_DEVEBOX) && LCD_W == 128
#define TYVOR_FC_ARM_UI
void tyvorFcArmModelLoaded(bool valid = true);
TyvorArmState tyvorHomeFcArm();
const char* tyvorFcArmStatusText();
const TyvorFcArmConfig& tyvorFcArmSettings();
void menuTyvorFcArm(uint16_t event);
#endif
