/* TYVOR power presentation, restricted to the DevEBox monochrome UI. */
#pragma once

#if defined(RADIO_SAOLALINKV1) && defined(SAOLALINK_DEVEBOX) && LCD_W == 128 && LCD_H == 64
#define TYVOR_POWER_UI

// Starting zero-frame may be painted during init; timed overlay starts only when
// normal menu processing is ready. One GUI refresh, no waits in this function.
bool drawTyvorStartup(bool interrupted);
// Original firmware owl/logo, without refreshing over the GUI's pending frame.
void drawTyvorSplashFrame();
// One fixed, licensed Ethnocentric TYVOR composition; no runtime font/glyphs.
void drawTyvorBrand(coord_t y);
// Draw into the existing 1 KiB framebuffer; the caller owns DMA/refresh.
void drawTyvorPowerFrame(uint32_t duration, uint32_t totalDuration,
                        bool shutdown, const char* message = nullptr);
void resetTyvorShutdown();
#endif
