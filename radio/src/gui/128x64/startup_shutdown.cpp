/*
 * Copyright (C) EdgeTX
 *
 * Based on code named
 *   opentx - https://github.com/opentx/opentx
 *   th9x - http://code.google.com/p/th9x
 *   er9x - http://code.google.com/p/er9x
 *   gruvin9x - http://code.google.com/p/gruvin9x
 *
 * License GPLv2: http://www.gnu.org/licenses/gpl-2.0.html
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 */

#include "edgetx.h"
#include "gui/128x64/tyvor_power.h"
#include "hal/rgbleds.h"
#include "boards/generic_stm32/rgb_leds.h"


#define SLEEP_BITMAP_WIDTH             42
#define SLEEP_BITMAP_HEIGHT            47

const unsigned char bmp_sleep[]  = {
#include "sleep.lbm"
};

#if defined(RADIO_FAMILY_T20)
constexpr uint8_t steps = NUM_FUNCTIONS_SWITCHES/2;
#elif defined(RADIO_GX12)
constexpr uint8_t steps = NUM_FUNCTIONS_SWITCHES - 2; //Exclude SA and SD
#elif defined(FUNCTION_SWITCHES)
constexpr uint8_t steps = NUM_FUNCTIONS_SWITCHES;
#endif

#if defined(TYVOR_POWER_UI)
static uint8_t tyvorShutdownProgress = 0;
static bool tyvorShutdownStarted = false;

void resetTyvorShutdown()
{
  tyvorShutdownProgress = 0;
  tyvorShutdownStarted = false;
}

// One clockwise perimeter, starting at twelve o'clock. A quarter needs only
// 32 bytes; integer rotations produce the other three. No float, heap or font.
static void drawTyvorPowerIcon(uint8_t count)
{
  static const int8_t arc[16][2] = {
    {0,-16}, {2,-16}, {3,-16}, {5,-15}, {6,-15}, {8,-14}, {9,-13}, {10,-12},
    {11,-11}, {12,-10}, {13,-9}, {14,-8}, {15,-6}, {15,-5}, {16,-3}, {16,-2}
  };
  for (uint8_t i = 0; i < 64; ++i) {
    int8_t x = arc[i % 16][0], y = arc[i % 16][1];
    for (uint8_t q = 0; q < i / 16; ++q) {
      const int8_t oldX = x; x = -y; y = oldX;
    }
    if (i < count)
      lcdDrawFilledRect(63 + x, 25 + y, 2, 2, SOLID, FORCE);
    // Inner power symbol: a broken circle and its fixed vertical stem.
    if (i >= 7 && i <= 57)
      lcdDrawFilledRect(63 + x * 9 / 16, 25 + y * 9 / 16, 2, 2, SOLID, FORCE);
  }
  lcdDrawFilledRect(63, 15, 2, 12, SOLID, FORCE);
}

void drawTyvorPowerFrame(uint32_t duration, uint32_t totalDuration,
                        bool shutdown, const char* message)
{
  lcdClear();
  uint8_t progress;
  if (shutdown)
    progress = totalDuration ? min<uint32_t>(64, uint64_t(min(duration, totalDuration)) * 64 / totalDuration) : 64;
  else {
    // Finish slightly early and hold the complete ring before the owl handoff.
    const uint32_t fillTicks = max<uint32_t>(1, totalDuration - min<uint32_t>(10, totalDuration / 12));
    progress = duration >= fillTicks ? 64 : uint64_t(duration) * 64 / fillTicks;
  }
  // Removing the tail of the clockwise arc moves its boundary counterclockwise.
  drawTyvorPowerIcon(shutdown ? 64 - progress : progress);
  lcdDrawText(LCD_W / 2, 49, shutdown ? "Shutting down..." : "Starting...", CENTERED | SMLSIZE);
  // Keep the existing model-powered warning visible during the power-button hold.
  if (message)
    lcdDrawText(LCD_W / 2, 58, message, SMLSIZE | CENTERED);
}
#endif

void drawStartupAnimation(uint32_t duration, uint32_t totalDuration)
{
  if (totalDuration == 0)
    return;

#if defined(TYVOR_POWER_UI)
  lcdRefreshWait();
  drawTyvorPowerFrame(duration, totalDuration, false);
  lcdRefresh();
  return;
#endif

  uint8_t index = limit<uint8_t>(0, duration / (totalDuration / 5), 4);

  lcdRefreshWait();
  lcdClear();

#if defined(FUNCTION_SWITCHES)
  uint8_t index2 = limit<uint8_t>(
      0, duration / (totalDuration / (steps + 1)),
      steps);

  for (uint8_t j = 0; j < steps; j++) {
    if (index2 > j) {
#if defined(FUNCTION_SWITCHES_RGB_LEDS)
      fsLedRGB(j, 0xFFFFFF);
      rgbLedColorApply();
#else
      fsLedOn(j);
#endif
#if defined(RADIO_FAMILY_T20)
      fsLedOn(j + steps);
#endif
    }
  }
#endif

  for (uint8_t i = 0; i < 4; i++) {
    if (index > i) {
      lcdDrawFilledRect(LCD_W / 2 - 18 + 10 * i, LCD_H / 2 - 3, 6, 6, SOLID, 0);
    }
  }

  lcdRefresh();
  lcdRefreshWait();
}

void drawShutdownAnimation(uint32_t duration, uint32_t totalDuration,
                           const char* message)
{
  if (totalDuration == 0)
    return;

#if defined(TYVOR_POWER_UI)
  // Animate at most one second of an existing hold; never change its deadline.
  uint32_t window = min<uint32_t>(totalDuration, 100);
  uint8_t progress = uint64_t(min(duration, window)) * 64 / window;
  if (tyvorShutdownStarted)
    tyvorShutdownProgress = max(tyvorShutdownProgress, progress);
  else
    tyvorShutdownStarted = true; // first visible frame is always a complete ring
  lcdRefreshWait();
  drawTyvorPowerFrame(tyvorShutdownProgress, 64, true, message);
  lcdRefresh();
  return;
#endif

  uint8_t index = limit<uint8_t>(0, duration / (totalDuration / 5), 4);

  lcdRefreshWait();
  lcdClear();

#if defined(FUNCTION_SWITCHES)

  uint8_t index2 = limit<uint8_t>(
      0, duration / (totalDuration / (steps + 1)),
      steps);

  for (uint8_t j = 0; j < steps; j++) {
#if defined(FUNCTION_SWITCHES_RGB_LEDS)
    fsLedRGB(j, 0);
    if (steps - index2 > j) {
        fsLedRGB(j, 0xFFFFFF);
    }
    rgbLedColorApply();
#else
    fsLedOff(j);
#if defined(RADIO_FAMILY_T20)
    fsLedOff(j + steps);
#endif
    if (steps - index2 > j) {
      fsLedOn(j);
#if defined(RADIO_FAMILY_T20)
      fsLedOn(j + steps);
#endif
    }
#endif
  }
#endif

  for (uint8_t i = 0; i < 4; i++) {
    if (4 - index > i) {
      lcdDrawFilledRect(LCD_W / 2 - 18 + 10 * i, LCD_H / 2 - 3, 6, 6, SOLID, 0);
    }
  }
#if defined(SAOLALINK_DEVEBOX)
  lcdDrawText(LCD_W / 2, 8, "TYVOR", DBLSIZE | CENTERED);
#endif
  if (message) {
    lcdDrawText((LCD_W - getTextWidth(message)) / 2, LCD_H-2*FH, message);
  }

  lcdRefresh();
  lcdRefreshWait();
}

void drawSleepBitmap()
{
  lcdRefreshWait();
#if defined(TYVOR_POWER_UI)
  // Continue the accepted shutdown; never return to the old boot splash.
  tyvorShutdownProgress = 64;
  drawTyvorPowerFrame(tyvorShutdownProgress, 64, true);
  lcdRefresh();
#else
  lcdClear();

  lcdDraw1bitBitmap((LCD_W - SLEEP_BITMAP_WIDTH) / 2,
                    (LCD_H - SLEEP_BITMAP_HEIGHT) / 2, bmp_sleep, 0);

  lcdRefresh();
#endif
  lcdRefreshWait();
}
