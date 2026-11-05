// DevEBox application-only DfuSe loader. Boot sectors are never writable.
#include "board.h"
#include "stm32_cmsis.h"
#include "flash_driver.h"
#include "hal/usb_driver.h"
#include "hal/abnormal_reboot.h"
#include "timers_driver.h"
#include "devebox_boot.h"
#include "thirdparty/STM32_USB_Device_Library/Class/DFU/Inc/usbd_dfu.h"
#include <string.h>

static volatile bool upload_claimed;
static bool update_started;
static bool update_failed;
static uint32_t next_address;
static uint32_t deferred_sp = 0xFFFFFFFF;
static uint32_t erased_sectors;
static volatile bool reset_pending;
static uint32_t reset_requested_at;

static uint32_t sector_start(uint32_t address)
{
  const uint32_t size = address < 0x08010000 ? 0x4000 :
                        address < 0x08020000 ? 0x10000 : 0x20000;
  return address & ~(size - 1U);
}

static uint32_t sector_bit(uint32_t address)
{
  // Physical sectors 2..7 form the application region on STM32F407VE.
  return 1U << (address < 0x08010000 ? (address - 0x08000000) / 0x4000 :
                address < 0x08020000 ? 4 : (address - 0x08000000) / 0x20000 + 4);
}

static bool app_range(uint32_t address, uint32_t len)
{
  return address >= APP_START_ADDRESS && address < DEVEBOX_APP_END &&
         len <= DEVEBOX_APP_END - address;
}

// Enumeration, GETSTATUS in idle, and USB scans must not hold the loader.
// dfu-util sends SET_ADDRESS before erasing/programming the application.
extern "C" void saolalinkDfuSetAddress(uint32_t address)
{
  if (app_range(address, 1)) upload_claimed = true;
}

static uint16_t init() { return USBD_OK; }
static uint16_t fail()
{
  update_failed = true;
  return USBD_FAIL;
}
static uint16_t erase(uint32_t address)
{
  if (reset_pending) return USBD_FAIL;
  if (!app_range(address, 1)) return fail();
  upload_claimed = true;
  // A new transfer must erase its vectors first. Keeping the initial SP erased
  // until manifestation makes power loss during erase/write recoverable.
  if (address == APP_START_ADDRESS) {
    update_started = true;
    update_failed = false;
    deferred_sp = 0xFFFFFFFF;
    next_address = APP_START_ADDRESS;
    erased_sectors = 0;
  }
  // dfu-util versions may erase all sectors first, or interleave erase/write.
  // Both are valid, but never erase a sector containing verified bytes.
  if (!update_started || update_failed || next_address > sector_start(address) ||
      stm32_flash_driver.erase_sector(address) < 0) return fail();
  erased_sectors |= sector_bit(address);
  return USBD_OK;
}
static uint16_t write(uint8_t* src, uint8_t* dest, uint32_t len)
{
  if (reset_pending) return USBD_FAIL;
  uint32_t address = (uint32_t)dest;
  if ((address & 3U) || !len || !app_range(address, len) ||
      !update_started || update_failed || address != next_address) return fail();
  upload_claimed = true;
  for (uint32_t a = address; a < address + len;) {
    if (!(erased_sectors & sector_bit(a))) return fail();
    const uint32_t size = a < 0x08010000 ? 0x4000 : a < 0x08020000 ? 0x10000 : 0x20000;
    a = sector_start(a) + size;
  }
  const uint32_t original_len = len;
  if (address == APP_START_ADDRESS) {
    uint32_t pc;
    if (len < 8) return fail();
    memcpy(&deferred_sp, src, 4);
    memcpy(&pc, src + 4, 4);
    if (!deveboxAppVectorsValid(deferred_sp, pc)) return fail();
    // The stack word is committed only by LeaveDFU, after all data is sent.
    address += 4;
    src += 4;
    len -= 4;
  }
  uint32_t words = len & ~3U;
  if (words && stm32_flash_driver.program(address, src, words) < 0) return fail();
  if (len != words) {
    uint32_t last = 0xFFFFFFFF;
    memcpy(&last, src + words, len - words);
    if (!app_range(address + words, 4) ||
        stm32_flash_driver.program(address + words, &last, 4) < 0) return fail();
  }
  // Verify each transfer against flash before allowing manifestation.
  if (memcmp((const void*)address, src, len)) return fail();
  next_address += original_len;
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

static void boot_app()
{
  // Reset flags are sticky. In particular an earlier watchdog flag must not
  // mask the software reset used to consume our one-shot app command.
  RCC->CSR |= RCC_CSR_RMVF;
  abnormalRebootSetCmd(DEVEBOX_BOOT_APP);
  NVIC_SystemReset();
}

static uint16_t leave(uint32_t)
{
  if (reset_pending) return USBD_OK;
  if (!update_started || update_failed || next_address < APP_START_ADDRESS + 8 ||
      !deveboxAppVectorsValid(deferred_sp, *(const uint32_t*)(APP_START_ADDRESS + 4)))
    return USBD_FAIL;
  if (stm32_flash_driver.program(APP_START_ADDRESS, &deferred_sp, 4) < 0 ||
      *(const uint32_t*)APP_START_ADDRESS != deferred_sp) return fail();
  // This callback runs inside the USB ISR, before the GETSTATUS control
  // transfer's status stage. Let that transfer and the host's final status
  // poll finish. Disconnect/reset only later from the foreground loop.
  reset_requested_at = timersGetMsTick();
  reset_pending = true;
  return USBD_OK;
}
static const USBD_DFU_MediaTypeDef media = {
  .pStrDesc = (uint8_t*)"@SaolaLink App /0x08008000/02*016Kg,01*064Kg,03*128Kg",
  .Init = init, .DeInit = init, .Erase = erase, .Write = write,
  .Read = read, .GetStatus = status, .LeaveDFU = leave,
};

void deveboxBootloaderDFU(bool stay)
{
  usbRegisterDFUMedia(&media);
  setSelectedUsbMode(USB_DFU_MODE);
  usbStart();
  const uint32_t started = timersGetMsTick();
  for (;;) {
    if (reset_pending && timersGetMsTick() - reset_requested_at >= DEVEBOX_MANIFEST_RESET_MS) {
      __disable_irq();
      usbStop();
      boot_app();
    }
    if (!stay && timersGetMsTick() - started >= DEVEBOX_UPLOAD_WINDOW_MS) {
      // Serialize timeout against USB callbacks: never reset after a claim,
      // including a request arriving on the last tick of the window.
      __disable_irq();
      if (!upload_claimed) {
        usbStop();
        boot_app();
      }
      __enable_irq();
    }
    __WFI();
  }
}
