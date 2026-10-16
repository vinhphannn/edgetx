#include "board.h"
#include "hal/key_driver.h"

#if defined(SAOLALINK_DEVEBOX)
#include "stm32_cmsis.h"
bool boardBLStartCondition()
{
  // The DevEBox PA0 key is active high. Also stay in recovery for blank/invalid app.
  RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN;
  (void)RCC->AHB1ENR;
  GPIOA->MODER &= ~3U;
  GPIOA->PUPDR = (GPIOA->PUPDR & ~3U) | 2U;
  const uint32_t sp = *(const uint32_t*)APP_START_ADDRESS;
  const uint32_t pc = *(const uint32_t*)(APP_START_ADDRESS + 4);
  const bool stack_ok = (sp > 0x20000000 && sp <= 0x20020000) ||
                        (sp > 0x10000000 && sp <= 0x10010000);
  const bool app_ok = stack_ok && (pc & 1) && pc >= APP_START_ADDRESS && pc < 0x08080000;
  return (GPIOA->IDR & 1) || !app_ok;
}
#elif defined(BOOTLOADER_KEYS)

bool boardBLStartCondition()
{
  // Trims combo activated
  pollKeys();
  bool result = (readTrims() == BOOTLOADER_KEYS);
#if defined(SECONDARY_BOOTLOADER_KEYS)
  result |= (readTrims() == SECONDARY_BOOTLOADER_KEYS);
#endif
  return result;
}

#elif (defined(RADIO_T8) || defined(RADIO_COMMANDO8)) && !defined(RADIOMASTER_RELEASE)

bool boardBLStartCondition()
{
  // Bind button pressed
  return (KEYS_GPIO_REG_BIND->IDR & KEYS_GPIO_PIN_BIND) == 0;
}

#endif
