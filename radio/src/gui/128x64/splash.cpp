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

const unsigned char splashdata[]  = {
  'S','P','S',0,
#if defined(SAOLALINK_DEVEBOX)
  #include "bitmaps/128x64/tyvor_owl.lbm"
#else
  #include "bitmaps/128x64/splash.lbm"
#endif
  'S','P','E',0 };

const unsigned char * const splash_lbm = splashdata+4;

#if defined(TYVOR_POWER_UI)
#if !defined(BOOT)
static const unsigned char tyvor_wordmark[] = {
  #include "bitmaps/128x64/tyvor_wordmark.lbm"
};
#endif

void drawTyvorBrand(coord_t y)
{
#if defined(BOOT)
  // The bootloader and its USB Connected screen retain their existing image.
  lcdDrawText(LCD_W / 2, y, "TYVOR", DBLSIZE | CENTERED);
#else
  lcdDraw1bitBitmap((LCD_W - tyvor_wordmark[0]) / 2, y, tyvor_wordmark, 0, INVERS);
#endif
}
#endif

static void drawSplashFrame()
{
  lcdClear();
#if defined(SAOLALINK_DEVEBOX)
  // The asset is white on black; the 1-bit encoder maps dark pixels to 1.
  lcdDraw1bitBitmap(0, 0, splash_lbm, 0, INVERS);
#if defined(TYVOR_POWER_UI)
  drawTyvorBrand(43);
#else
  lcdDrawText(LCD_W / 2, 43, "TYVOR", DBLSIZE | CENTERED);
#endif
#else
  lcdDraw1bitBitmap(0, 0, splash_lbm, 0, 0);
#endif
}

#if defined(TYVOR_POWER_UI)
void drawTyvorSplashFrame()
{
  drawSplashFrame();
}
#endif

void drawSplash()
{
  drawSplashFrame();
  lcdRefresh();
}
