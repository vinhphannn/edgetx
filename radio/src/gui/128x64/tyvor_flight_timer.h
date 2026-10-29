/* Independent, monotonic flight clock. It never writes Timer1 or control data. */
#pragma once
#include <stdint.h>
#include <stdio.h>
#include "tyvor_flight_data.h"

enum class TyvorFlightTimerMode : uint8_t { Auto, Switch };

struct TyvorFlightTimerConfig {
  TyvorFlightTimerMode mode = TyvorFlightTimerMode::Auto;
  int16_t switchSource = 0;
  uint8_t sensor = 0;  // 1-based, zero means no verified FC source.
  uint16_t sensorId = 0;
  uint8_t instance = 0, subId = 0;
  uint16_t modules = 0;
  bool verified = false;
};

inline bool tyvorDecodeFlightConfig(const char* text, TyvorFlightTimerConfig& out)
{
  if (!text) return false;
  int32_t v[9];
  for (unsigned i=0; i<9; ++i) {
    bool negative = *text == '-';
    if (negative) ++text;
    if (*text < '0' || *text > '9') return false;
    uint32_t n=0;
    do { n=n*10+(*text++-'0'); if (n>65535) return false; } while (*text>='0' && *text<='9');
    v[i]=negative ? -int32_t(n) : int32_t(n);
    if (i<8) { if (*text++!=',') return false; }
    else if (*text) return false;
  }
  if (v[0]!=1 || v[1]<0 || v[1]>1 || v[2]<-32768 || v[2]>32767 ||
      v[3]<0 || v[3]>255 || v[4]<0 || v[5]<0 || v[5]>255 ||
      v[6]<0 || v[6]>255 || v[7]<0 || v[8]<0 || v[8]>1) return false;
  out.mode=TyvorFlightTimerMode(v[1]); out.switchSource=v[2]; out.sensor=v[3];
  out.sensorId=v[4]; out.instance=v[5]; out.subId=v[6]; out.modules=v[7]; out.verified=v[8];
  return true;
}

inline void tyvorEncodeFlightConfig(char (&text)[64], const TyvorFlightTimerConfig& c)
{
  snprintf(text,sizeof(text),"1,%u,%d,%u,%u,%u,%u,%u,%u",unsigned(c.mode),
           int(c.switchSource),unsigned(c.sensor),unsigned(c.sensorId),
           unsigned(c.instance),unsigned(c.subId),unsigned(c.modules),unsigned(c.verified));
}

class TyvorFlightClock {
 public:
  uint32_t elapsed = 0;  // 10 ms units, saturates rather than wrapping duration.
  bool ready = false, hasTime = false, running = false;
  TyvorArmState previous = TyvorArmState::Unknown;
  TyvorArmState lastConfirmed = TyvorArmState::Unknown;

  void clear(uint32_t now, bool showZero=false) {
    elapsed=0; ready=false; hasTime=showZero; running=false;
    previous=lastConfirmed=TyvorArmState::Unknown; lastTick=now;
  }
  void update(uint32_t now, TyvorArmState signal) {
    const uint32_t dt=now-lastTick; lastTick=now;
    if (running && previous==TyvorArmState::Armed && signal!=TyvorArmState::Unknown) {
      elapsed = UINT32_MAX-elapsed < dt ? UINT32_MAX : elapsed+dt;
    }
    if (signal==TyvorArmState::Unknown) {
      // Retain lastConfirmed across telemetry gaps: reconnect ON is not a new flight.
      previous=signal; return;
    }
    if (signal==TyvorArmState::Disarmed) {
      running=false; ready=true; hasTime=true;
    }
    else if (lastConfirmed!=TyvorArmState::Armed && ready) {
      elapsed=0; running=true; hasTime=true;
    }
    lastConfirmed=signal; previous=signal;
  }
  uint32_t seconds() const { return elapsed/100; }
 private:
  uint32_t lastTick=0;
};

#if defined(RADIO_SAOLALINKV1) && defined(SAOLALINK_DEVEBOX) && LCD_W == 128
#define TYVOR_FLIGHT_TIMER_UI
void tyvorFlightTimerModelLoaded(bool valid=true);
void tyvorFlightTimerPoll();
void tyvorFlightTimerReset();
TyvorArmState tyvorFlightTimerArm();
bool tyvorFlightTimerHasTime();
uint32_t tyvorFlightTimerSeconds();
const char* tyvorFlightTimerTag();
const TyvorFlightTimerConfig& tyvorFlightTimerSettings();
void menuTyvorFlightTimer(uint16_t event);
#endif
