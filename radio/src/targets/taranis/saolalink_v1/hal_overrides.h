#pragma once

#if defined(SAOLALINK_DEVEBOX)
// Six-pin external SPI socket has no card-detect contact.
#undef SD_PRESENT_GPIO

// External 128x64 SSD1309 SPI module, powered directly by its 5V supply.
// Retain Pocket SPI3 pins; this module has no MCU-controlled OLED supply pin.
#define SSD1309_LCD
#define SAOLALINK_OLED_ROTATE_180
#undef OLED_SCREEN
#define OLED_SCREEN true
#undef LCD_SPI_PRESCALER
#define LCD_SPI_PRESCALER (SPI_CR1_BR_1 | SPI_CR1_BR_0) // APB1 / 16 = 2.625 MHz
#endif

// SaolaLink V1 currently inherits the Pocket-compatible shared HAL.
// Override non-JSON peripherals here, e.g.:
// #undef INTMODULE_PWR_GPIO
// #define INTMODULE_PWR_GPIO GPIO_PIN(GPIOC, 4)
// Review timer/DMA conflicts together with GPIO changes.
