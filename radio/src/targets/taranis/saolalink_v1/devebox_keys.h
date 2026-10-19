#pragma once

#include "hal/gpio.h"
#include "hal/key_driver.h"
#include "stm32_gpio.h"

// Wired navigation keys, including Enter on PD14, not Pocket Enter (PA13).
// Do not initialize trims: PC1/PC2 are now the DevEBox RV/RH ADC inputs.
struct DeveboxKey {
  gpio_t gpio;
  EnumKeys key;
  const char* name;
  const char* pin;
};
static const DeveboxKey deveboxKeys[] = {
  {GPIO_PIN(GPIOC, 5), KEY_EXIT, "RTN", "PC5"},
  {GPIO_PIN(GPIOD, 3), KEY_PAGEUP, "PAGE<", "PD3"},
  {GPIO_PIN(GPIOD, 7), KEY_PAGEDN, "PAGE>", "PD7"},
  {GPIO_PIN(GPIOD, 2), KEY_TELE, "TELE", "PD2"},
  {GPIO_PIN(GPIOE, 10), KEY_SYS, "SYS", "PE10"},
  {GPIO_PIN(GPIOE, 11), KEY_MODEL, "MDL", "PE11"},
  {GPIO_PIN(GPIOD, 14), KEY_ENTER, "ENTER", "PD14"},
};
static constexpr unsigned deveboxKeyCount = sizeof(deveboxKeys) / sizeof(deveboxKeys[0]);

static inline uint32_t deveboxReadButtons()
{
  uint32_t pressed = 0;
  for (unsigned i = 0; i < deveboxKeyCount; ++i)
    if (!gpio_read(deveboxKeys[i].gpio)) pressed |= 1U << i;
  return pressed;
}
