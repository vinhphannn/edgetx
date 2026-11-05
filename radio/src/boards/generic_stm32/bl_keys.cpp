#include "board.h"
#include "hal/key_driver.h"

#if defined(SAOLALINK_DEVEBOX)
#include "stm32_cmsis.h"
#include "targets/taranis/saolalink_v1/devebox_boot.h"
void boardBLEarlyInit()
{
  // RTN (PC5) is active LOW. Set its pull-up before the boot input settling
  // delay, without initializing application keys, trims or analog pins.
  RCC->AHB1ENR |= RCC_AHB1ENR_GPIOCEN;
  (void)RCC->AHB1ENR;
  GPIOC->MODER &= ~(3U << (5 * 2));
  GPIOC->PUPDR = (GPIOC->PUPDR & ~(3U << (5 * 2))) | (1U << (5 * 2));
#if defined(SAOLALINK_DEVEBOX_V2) && defined(RTCLOCK)
  // Let the RTC crystal settle during the USB upload window. Do not wait for
  // LSERDY here, reset the backup domain, or change the existing RTC source.
  RCC->APB1ENR |= RCC_APB1ENR_PWREN;
  (void)RCC->APB1ENR;
  PWR->CR |= PWR_CR_DBP;
  (void)PWR->CR;
  RCC->BDCR |= RCC_BDCR_LSEON;
#endif
}

bool boardBLStartCondition()
{
  // Sample only at startup. Also stay in recovery for blank/invalid app.
  const uint32_t sp = *(const uint32_t*)APP_START_ADDRESS;
  const uint32_t pc = *(const uint32_t*)(APP_START_ADDRESS + 4);
  const bool app_ok = deveboxAppVectorsValid(sp, pc);
  return !(GPIOC->IDR & (1U << 5)) || !app_ok;
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
