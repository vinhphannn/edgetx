/*
 * Copyright (C) EdgeTx
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

#include "hal/key_driver.h"

#include "stm32_hal_ll.h"
#include "stm32_gpio_driver.h"

#include "stm32_keys.inc"
#if defined(SAOLALINK_DEVEBOX)
#include "targets/taranis/saolalink_v1/devebox_keys.h"
#endif

#define __weak __attribute__((weak))

__weak void keysInit()
{
#if defined(SAOLALINK_DEVEBOX)
  for (const auto& key : deveboxKeys)
    gpio_init(key.gpio, GPIO_IN_PU, GPIO_PIN_SPEED_LOW);
#else
  _init_keys();
  _init_trims();
#endif
}

__weak void pollKeys()
{
}

__weak uint32_t readKeys()
{
#if defined(SAOLALINK_DEVEBOX)
  uint32_t result = 0;
  uint32_t pressed = deveboxReadButtons();
  for (unsigned i = 0; i < deveboxKeyCount; ++i)
    if (pressed & (1U << i)) result |= 1U << deveboxKeys[i].key;
  return result;
#endif
  return _read_keys();
}

__weak uint32_t readTrims()
{
#if defined(SAOLALINK_DEVEBOX)
  return 0;
#endif
  return _read_trims();
}
