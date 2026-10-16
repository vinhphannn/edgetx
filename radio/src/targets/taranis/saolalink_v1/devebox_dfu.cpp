// DevEBox adaptation of EdgeTX's USB DFU media API. Boot sectors are not writable.
#include "board.h"
#include "stm32_cmsis.h"
#include "flash_driver.h"
#include "hal/usb_driver.h"
#include "thirdparty/STM32_USB_Device_Library/Class/DFU/Inc/usbd_dfu.h"
#include <string.h>

static constexpr uint32_t end_address = 0x08080000;
static bool app_range(uint32_t address, uint32_t len)
{
  return address >= APP_START_ADDRESS && address < end_address &&
         len <= end_address - address;
}
static uint16_t init() { return USBD_OK; }
static uint16_t erase(uint32_t address)
{
  if (!app_range(address, 1)) return USBD_FAIL;
  return stm32_flash_driver.erase_sector(address) < 0 ? USBD_FAIL : USBD_OK;
}
static uint16_t write(uint8_t* src, uint8_t* dest, uint32_t len)
{
  uint32_t address = (uint32_t)dest;
  if ((address & 3U) || !app_range(address, len)) return USBD_FAIL;
  // F4 driver programs words. Never read past the final USB transfer or
  // program stale bytes after a non-word-sized application image.
  uint32_t words = len & ~3U;
  if (words && stm32_flash_driver.program(address, src, words) < 0)
    return USBD_FAIL;
  if (len != words) {
    uint32_t last = 0xFFFFFFFF;
    memcpy(&last, src + words, len - words);
    if (!app_range(address + words, 4) ||
        stm32_flash_driver.program(address + words, &last, 4) < 0)
      return USBD_FAIL;
  }
  return USBD_OK;
}
static uint8_t* read(uint8_t* src, uint8_t* dest, uint32_t len)
{
  if (!app_range((uint32_t)src, len)) return nullptr;
  memcpy(dest, src, len);
  return dest;
}
static uint16_t status(uint32_t address, uint8_t cmd, uint8_t* buffer)
{
  if (!app_range(address, 1)) return USBD_FAIL;
  uint32_t timeout = cmd == DFU_MEDIA_ERASE ? 2000 : 20;
  buffer[1] = timeout; buffer[2] = timeout >> 8; buffer[3] = timeout >> 16;
  return USBD_OK;
}
static const USBD_DFU_MediaTypeDef media = {
  .pStrDesc = (uint8_t*)"@SaolaLink App /0x08008000/02*016Kg,01*064Kg,03*128Kg",
  .Init = init, .DeInit = init, .Erase = erase, .Write = write,
  .Read = read, .GetStatus = status,
};

void deveboxBootloaderDFU()
{
  usbRegisterDFUMedia(&media);
  setSelectedUsbMode(USB_DFU_MODE);
  usbStart();
  // Reset after upload to start EdgeTX; PA0+RESET re-enters this loader.
  for (;;) __WFI();
}
