#pragma once

#include <stdint.h>

// One-shot reset handoff: start the app before bringing USB/timers up again.
static constexpr uint32_t DEVEBOX_BOOT_APP = 0x534C4150;
static constexpr uint32_t DEVEBOX_APP_END = 0x08080000;
#if defined(SAOLALINK_DEVEBOX_V2)
static constexpr uint32_t DEVEBOX_UPLOAD_WINDOW_MS = 500;
#else
static constexpr uint32_t DEVEBOX_UPLOAD_WINDOW_MS = 2000;
#endif
static constexpr uint32_t DEVEBOX_MANIFEST_RESET_MS = 250;

static inline bool deveboxAppVectorsValid(uint32_t sp, uint32_t pc)
{
  const bool stack_ok = !(sp & 7U) &&
      ((sp > 0x20000000 && sp <= 0x20020000) ||
       (sp > 0x10000000 && sp <= 0x10010000));
  return stack_ok && (pc & 1U) && pc >= APP_START_ADDRESS && pc < DEVEBOX_APP_END;
}
