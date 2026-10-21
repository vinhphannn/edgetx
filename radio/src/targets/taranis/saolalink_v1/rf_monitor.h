#pragma once

#include <stdint.h>

// Diagnostic counters only. Never print, allocate or change protocol in ISR paths.
struct DeveboxRFMonitor {
  volatile uint32_t txQueued = 0, rxBytes = 0, goodFrames = 0;
  volatile uint32_t crcErrors = 0, framingDrops = 0, lastGoodMs = 0, baud = 0;
  volatile bool uartReady = false, seenThisSession = false;

  void beginSession(uint32_t rate) {
    baud = rate;
    uartReady = false;
    seenThisSession = false;
    rxAtStart = rxBytes;
  }
  void validFrame(uint32_t now) {
    ++goodFrames;
    lastGoodMs = now;
    seenThisSession = true;
  }
  enum Link { OFF, UART_DOWN, WAIT_RX, BAD_RX, OK, STALE };
  Link link(bool powered, uint32_t now) const {
    if (!powered) return OFF;
    if (!uartReady) return UART_DOWN;
    if (seenThisSession) return uint32_t(now - lastGoodMs) <= 2000 ? OK : STALE;
    return rxBytes != rxAtStart ? BAD_RX : WAIT_RX;
  }

 private:
  uint32_t rxAtStart = 0;
};

extern DeveboxRFMonitor deveboxRF;
