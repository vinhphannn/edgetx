/* Fixed-width presentation helpers for the TYVOR monochrome HOME. */
#pragma once

#include <stdint.h>
#include <stdio.h>

// Use the existing Radio / Hardware Battery Range (0.1 V units), not an
// assumed chemistry, cell count or percentage. Untouched 9-12 V defaults do
// not establish a battery profile on DevEBox, so retain the unknown indicator.
inline int8_t tyvorRadioBatteryBars(uint8_t voltage, int8_t minOffset, int8_t maxOffset)
{
  const int16_t low = 90 + minOffset, high = 120 + maxOffset;
  if (!voltage || (!minOffset && !maxOffset) || low < 30 || high > 160 || high <= low)
    return -1;
  if (voltage <= low) return 0;
  if (voltage >= high) return 5;
  return ((voltage - low) * 5 + (high - low) / 2) / (high - low);
}

// Map a real, signed control value into a bounded display rail. The caller
// chooses orientation; no input, calibration or mixer value is modified.
inline int16_t tyvorHomePosition(int32_t value, int16_t origin, int16_t travel,
                                 int16_t range = 1024)
{
  if (value < -range) value = -range;
  if (value > range) value = range;
  return origin + (value + range) * travel / (2 * range);
}

// Use an unsigned magnitude so even a corrupted INT32_MIN cannot overflow or
// turn into an unbounded string. Long persistent timers use hours, as EdgeTX does.
inline void tyvorHomeTimerText(char (&text)[16], int32_t value)
{
  const char *sign = value < 0 ? "-" : "";
  const uint32_t magnitude = value < 0 ? 0u - uint32_t(value) : uint32_t(value);
  if (magnitude < 3600)
    snprintf(text, sizeof(text), "%s%02lu:%02lu", sign,
             (unsigned long)(magnitude / 60), (unsigned long)(magnitude % 60));
  else if (magnitude < 360000)
    snprintf(text, sizeof(text), "%s%02luh%02lu", sign,
             (unsigned long)(magnitude / 3600), (unsigned long)(magnitude / 60 % 60));
  else
    snprintf(text, sizeof(text), "%s%luh", sign, (unsigned long)(magnitude / 3600));
}
