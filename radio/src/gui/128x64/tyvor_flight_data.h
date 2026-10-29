/* Read-only presentation values for TYVOR HOME. No control/arming decisions. */
#pragma once

#include <stdint.h>
#include <stdio.h>

enum class TyvorArmState : uint8_t { Unknown, Disarmed, Armed };

struct TyvorFlightData {
  // Only an explicitly confirmed FC status provider may set this value.
  // Neither the timer switch nor unconfirmed flight-mode text proves ARM.
  TyvorArmState arm = TyvorArmState::Unknown;
  bool batteryValid = false;
  bool satellitesValid = false;
  bool altitudeValid = false;
  bool powerValid = false;
  bool powerDbm = false;
  bool batteryPercentValid = false;
  bool modeValid = false;
  bool linkQualityValid = false;
  uint8_t linkQuality = 0;
  uint8_t batteryPercent = 0;
  char mode[17] = {};
  uint16_t batteryDecivolts = 0;
  uint8_t satellites = 0;
  int32_t power = 0;
  int32_t altitudeMeters = 0; // CRSF 0x09: above FC start/calibration point.
};

inline bool tyvorFlightSensorFresh(bool streaming, int timeout, int start = 125,
                                   int maxAge = 31)
{
  // Numeric flight information expires on this HOME after about five seconds,
  // even if another sensor keeps the telemetry link active (31 * 160 ms).
  return streaming && timeout >= 0 && timeout <= start && start - timeout <= maxAge;
}

// Use a monotonic receive timestamp as well as the legacy availability flags.
// The legacy 160 ms timeout tick is derived from a counter reset by RF link
// packets; its cadence alone cannot bound FC sensor age under all link rates.
inline bool tyvorFlightReceivedRecently(uint32_t now, uint32_t receivedAt,
                                       uint16_t maxAge = 31 * 16)
{
  return uint32_t(now - receivedAt) <= maxAge;
}

inline bool tyvorFlightModeText(const char *source, uint8_t limit, char (&dest)[17])
{
  dest[0] = '\0';
  if (limit > 16) limit = 16;
  uint8_t length = 0;
  while (length < limit && source[length]) {
    const unsigned char c = source[length];
    if (c < ' ' || c > '~') { dest[0] = '\0'; return false; }
    dest[length] = c;
    ++length;
  }
  while (length && dest[length - 1] == ' ') --length;
  uint8_t first = 0;
  while (first < length && dest[first] == ' ') ++first;
  for (uint8_t i = first; i < length; ++i) dest[i - first] = dest[i];
  dest[length - first] = '\0';
  return length > first;
}

// Remove one terminal disarm marker from a display copy only. Raw FM is intact.
inline void tyvorHomeModeLabel(const char* source, char (&dest)[17])
{
  unsigned length = 0;
  while (length < 16 && source[length]) { dest[length] = source[length]; ++length; }
  if (length > 1 && dest[length - 1] == '*' && dest[length - 2] != '*') --length;
  dest[length] = '\0';
}

// Five discrete display levels, nearest integer; never derived from RF power.
inline int8_t tyvorHomeLinkBars(const TyvorFlightData& data)
{
  if (!data.linkQualityValid || data.linkQuality > 100) return -1;
  return (unsigned(data.linkQuality) * 5 + 50) / 100;
}

inline int8_t tyvorDroneBatteryBars(const TyvorFlightData &data)
{
  // Only the FC's explicitly reported percentage drives these bars. Voltage
  // alone cannot establish charge without confirmed chemistry/cell thresholds.
  if (!data.batteryValid || !data.batteryPercentValid || data.batteryPercent > 100)
    return -1;
  if (!data.batteryPercent) return 0;
  return (data.batteryPercent + 19) / 20;
}

inline bool tyvorFlightVoltage(int32_t value, uint8_t precision, uint16_t &result)
{
  if (value < 0 || precision > 3) return false;
  const uint32_t divisors[] = {1, 1, 10, 100};
  uint32_t v = uint32_t(value);
  if (!precision) {
    if (v > 999) return false;
    v *= 10;
  }
  else {
    const uint32_t divisor = divisors[precision];
    if (v > 9999 * divisor) return false;
    v = (v + divisor / 2) / divisor;
  }
  if (v > 9999) return false;
  result = uint16_t(v);
  return true;
}

inline const char *tyvorArmLabel(TyvorArmState state)
{
  switch (state) {
    case TyvorArmState::Armed: return "ARMED";
    case TyvorArmState::Disarmed: return "DISARMED";
    default: return "UNKNOWN";
  }
}

inline void tyvorFlightBatteryText(char (&text)[16], const TyvorFlightData &data)
{
  if (data.batteryValid)
    snprintf(text, sizeof(text), "%u.%uV", unsigned(data.batteryDecivolts / 10),
             unsigned(data.batteryDecivolts % 10));
  else snprintf(text, sizeof(text), "--");
}

inline void tyvorFlightSatsText(char (&text)[16], const TyvorFlightData &data)
{
  // Count only; a satellite count does not establish GPS fix or readiness.
  if (data.satellitesValid) snprintf(text, sizeof(text), "%u", unsigned(data.satellites));
  else snprintf(text, sizeof(text), "--");
}

inline bool tyvorFlightAltitudeMeters(int32_t value, uint8_t precision, int32_t& meters)
{
  if (precision > 3) return false;
  const int32_t scales[] = {1, 10, 100, 1000};
  const int32_t scale = scales[precision];
  // CRSF 0x09 range; 0xffff / 32767m is the invalid upper sentinel.
  if (value < -1000 * scale || value > 32766 * scale) return false;
  meters = value / scale; // Whole metres, truncation towards zero; no radio zeroing.
  return true;
}

inline void tyvorFlightAltitudeText(char (&text)[16], const TyvorFlightData &data)
{
  if (data.altitudeValid && data.altitudeMeters >= -1000 && data.altitudeMeters <= 32766)
    snprintf(text, sizeof(text), "%ldm", (long)data.altitudeMeters);
  else snprintf(text, sizeof(text), "--");
}

inline void tyvorFlightPowerText(char (&text)[16], const TyvorFlightData &data)
{
  if (!data.powerValid) snprintf(text, sizeof(text), "--");
  else if (data.powerDbm) snprintf(text, sizeof(text), "%lddBm", (long)data.power);
  else if (data.power >= 10000)
    snprintf(text, sizeof(text), "%ldW", (long)((data.power + 500) / 1000));
  else if (data.power >= 1000)
    snprintf(text, sizeof(text), "%ld.%ldW", (long)(data.power / 1000),
             (long)((data.power % 1000) / 100));
  else snprintf(text, sizeof(text), "%ldmW", (long)data.power);
}
