#pragma once

#if defined(SAOLALINK_DEVEBOX_V2)
// External main-power latch: active-high NPN drive and active-low sense.
#undef PWR_ON_GPIO
#define PWR_ON_GPIO GPIO_PIN(GPIOD, 0)
#undef PWR_SWITCH_GPIO
#define PWR_SWITCH_GPIO GPIO_PIN(GPIOD, 1)

// BOOT circuitry is not verified. Do not clamp ESP32 GPIO0 LOW or back-power it.
#define SAOLALINK_RF_BOOT_GPIO GPIO_PIN(GPIOB, 1)
#undef INTMODULE_BOOTCMD_GPIO

// Six-pin external SPI socket has no card-detect contact.
#undef SD_PRESENT_GPIO

// Keep PE10 for SYS. Encoder uses PE9 and PE14, including EXTI remapping.
#undef ROTARY_ENCODER_GPIO_PIN_B
#define ROTARY_ENCODER_GPIO_PIN_B LL_GPIO_PIN_14
#undef ROTARY_ENCODER_POSITION
#define ROTARY_ENCODER_POSITION (((ROTARY_ENCODER_GPIO->IDR >> 9) & 1U) | ((ROTARY_ENCODER_GPIO->IDR >> 13) & 2U))
#undef ROTARY_ENCODER_EXTI_LINE2
#define ROTARY_ENCODER_EXTI_LINE2 LL_EXTI_LINE_14
#undef ROTARY_ENCODER_EXTI_SYS_LINE2
#define ROTARY_ENCODER_EXTI_SYS_LINE2 LL_SYSCFG_EXTI_LINE14

// Use the same SSD1309 SPI3 driver, wiring and orientation as DevEBox Base.
// SCK PC10, MOSI PC12, DC PC11, CS PA15, RESET PD12; module power 5 V.
#define SSD1309_LCD
#undef SAOLALINK_OLED_ROTATE_180
#undef OLED_SCREEN
#define OLED_SCREEN true
#undef LCD_SPI_PRESCALER
#define LCD_SPI_PRESCALER (SPI_CR1_BR_1 | SPI_CR1_BR_0) // APB1 / 16 = 2.625 MHz
#endif
