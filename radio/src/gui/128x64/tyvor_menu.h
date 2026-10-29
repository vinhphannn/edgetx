/* TYVOR menu visibility only. Never changes trainer data, PPM or mixer state. */
#pragma once
#include <stdint.h>

#if defined(RADIO_SAOLALINKV1) && LCD_W == 128
#define TYVOR_HIDE_TRAINER
#endif

inline bool tyvorTrainerPageEnabled()
{
#if defined(TYVOR_HIDE_TRAINER)
  return false;
#else
  return radioTrainerEnabled();
#endif
}

constexpr uint8_t tyvorTrainerRow(uint8_t visible)
{
#if defined(TYVOR_HIDE_TRAINER)
  (void)visible;
  return HIDDEN_ROW;
#else
  return visible;
#endif
}
