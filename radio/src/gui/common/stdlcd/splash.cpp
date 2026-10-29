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
#include "inactivity_timer.h"
#include "os/sleep.h"

static bool splashStarted = false;
#if defined(TYVOR_POWER_UI)
static bool tyvorStartupReady = false;
static tmr10ms_t tyvorStartupStart;
static tmr10ms_t tyvorStartupElapsed = 0;

bool drawTyvorStartup(bool interrupted)
{
  // A cancelled power-button hold must start its next animation at a full ring again.
  resetTyvorShutdown();
  if (!splashStarted || !tyvorStartupReady)
    return false;
  // Monotonic, single-shot presentation even if the caller repeats a frame.
  tmr10ms_t elapsed = get_tmr10ms() - tyvorStartupStart;
  elapsed = tyvorStartupElapsed = max(elapsed, tyvorStartupElapsed);
  if (interrupted || elapsed >= 270) {
    splashStarted = tyvorStartupReady = false;
    return false;
  }
  if (elapsed < 120)
    drawTyvorPowerFrame(elapsed, 120, false);
  else
    drawTyvorSplashFrame();  // Original owl for 150 ticks, then idle HOME.
  return true;
}
#endif

void startSplash()
{
  splashStarted = true;
#if defined(TYVOR_POWER_UI)
  tyvorStartupReady = false;
#endif
}

void cancelSplash()
{
  splashStarted = false;
#if defined(TYVOR_POWER_UI)
  tyvorStartupReady = false;
#endif
}

void waitSplash()
{
#if defined(TYVOR_POWER_UI)
  // Arm a UI overlay instead of waiting here. Startup checks, calibration,
  // mixer initialisation and watchdog setup retain their normal execution order.
  tyvorStartupReady = splashStarted && SPLASH_NEEDED();
  tyvorStartupStart = get_tmr10ms();
  tyvorStartupElapsed = 0;
#else
  // Handle B&W splash screen

#if defined(PWR_BUTTON_PRESS)
  bool refresh = false;
#endif

  if (SPLASH_NEEDED() && splashStarted) {
    resetBacklightTimeout();
    drawSplash();

    getADC(); // init ADC array

    inactivityCheckInputs();

    tmr10ms_t tgtime = get_tmr10ms() + SPLASH_TIMEOUT;

    while (tgtime > get_tmr10ms()) {
      sleep_ms(1);

      getADC();

      if (getEvent() || inactivityCheckInputs())
        return;

#if defined(PWR_BUTTON_PRESS)
      uint32_t pwr_check = pwrCheck();
      if (pwr_check == e_power_off) {
        break;
      }
      else if (pwr_check == e_power_press) {
        refresh = true;
      }
      else if (pwr_check == e_power_on && refresh) {
        drawSplash();
        refresh = false;
      }
#else
      if (pwrCheck() == e_power_off) {
        return;
      }
#endif

      checkBacklight();
    }
  }
#endif
}
