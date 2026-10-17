#pragma once

#include "hal/gpio.h"
#include "hal/key_driver.h"
#include "stm32_gpio.h"

// Only the six wired navigation keys. Do not initialize Pocket Enter (PA13)
// or trims on ADC pins reserved for the upcoming gimbal wiring.
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
};

static inline uint32_t deveboxReadButtons()
{
  uint32_t pressed = 0;
  for (unsigned i = 0; i < 6; ++i)
    if (!gpio_read(deveboxKeys[i].gpio)) pressed |= 1U << i;
  return pressed;
}
