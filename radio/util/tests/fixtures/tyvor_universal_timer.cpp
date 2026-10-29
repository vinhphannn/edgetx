// Synthetic input fixtures against actual firmware objects; not physical FC evidence.
#include "edgetx.h"
#include "gui/128x64/tyvor_flight_timer.h"
#include "hal/switch_driver.h"
#include "telemetry/crossfire.h"
#include "timers.h"
#include <cassert>
#include <cstdio>
#include <cstring>
extern void simuSetSwitch(uint8_t,int8_t);
extern void boardInitSwitches();
extern TyvorFlightData homeData() asm("_ZL23readTyvorHomeFlightDatav");
extern void homeDraw() asm("_ZL13drawTyvorHomev");
static unsigned cases;
static void pass(const char*s){++cases;printf("PASS %s\n",s);fflush(stdout);}
static void save(const TyvorFlightTimerConfig& c){char text[64];tyvorEncodeFlightConfig(text,c);assert(g_model.setUserData("TYVOR.FlightTimer.v1",text));tyvorFlightTimerModelLoaded();}
static void tick(unsigned n=100){g_tmr10ms+=n;tyvorFlightTimerPoll();}
static void fresh(int value){telemetryStreaming=100;telemetryItems[0].value=value;telemetryItems[0].setFresh();}
static void known(int v,unsigned dt=100){g_tmr10ms+=dt;fresh(v);tyvorFlightTimerPoll();}
extern "C" int __wrap_main(int,char**){
 memset(&g_model,0,sizeof(g_model));memset(&g_eeGeneral,0,sizeof(g_eeGeneral));
 for(auto& i:telemetryItems)i.clear();
 switchInit();boardInitSwitches();g_eeGeneral.switchSetType(0,SWITCH_3POS);
 TyvorFlightTimerConfig c;c.mode=TyvorFlightTimerMode::Switch;c.switchSource=SWSRC_FIRST_SWITCH+2;
 save(c);simuSetSwitch(0,-1);tick();assert(tyvorFlightTimerHasTime());
 simuSetSwitch(0,1);tick();assert(tyvorFlightTimerSeconds()==0);tick(251);assert(tyvorFlightTimerSeconds()==2);
 assert(homeData().arm==TyvorArmState::Unknown);pass("SWITCH physical-source mapping counts without claiming FC ARM");
 simuSetSwitch(0,-1);tick(49);assert(tyvorFlightTimerSeconds()==3);tick(500);assert(tyvorFlightTimerSeconds()==3);
 simuSetSwitch(0,1);tick();assert(!tyvorFlightTimerSeconds());tick();assert(tyvorFlightTimerSeconds()==1);pass("OFF holds; next ON starts a new flight");
 telemetryStreaming=0;tick(100);assert(tyvorFlightTimerSeconds()==2);pass("SWITCH works without telemetry");
 tyvorFlightTimerReset();tick(400);assert(tyvorFlightTimerSeconds()==0);simuSetSwitch(0,-1);tick();simuSetSwitch(0,1);tick();tick();assert(tyvorFlightTimerSeconds()==1);pass("manual reset requires OFF before a new start");
 auto original=g_model;auto t0=timersStates[0];lcdClear();homeDraw();assert(!memcmp(&original,&g_model,sizeof(original)));assert(!memcmp(&t0,&timersStates[0],sizeof(t0)));pass("HOME rendering and flight clock leave Timer1/model/control fields unchanged");
 tyvorFlightTimerModelLoaded();tick(500);assert(!tyvorFlightTimerHasTime());assert(tyvorFlightTimerSettings().switchSource==c.switchSource);pass("model/reboot reload preserves config, resets runtime, refuses initial ON");
 c.switchSource=-(SWSRC_FIRST_SWITCH+2);save(c);simuSetSwitch(0,1);tick();simuSetSwitch(0,-1);tick();tick();assert(tyvorFlightTimerSeconds()==1);pass("per-model inverted switch source is honored");
 g_model.clearUserData();tyvorFlightTimerModelLoaded();tick();assert(!tyvorFlightTimerHasTime());assert(tyvorFlightTimerSettings().mode==TyvorFlightTimerMode::Auto);pass("another/unconfigured model does not inherit the previous switch");
 g_model.moduleData[0].type=MODULE_TYPE_CROSSFIRE;
 auto& s=g_model.telemetrySensors[0];memset(&s,0,sizeof(s));s.id=0x80a0;s.instance=1;s.unit=UNIT_RAW;memcpy(s.label,"FARM",4);
 c={};c.mode=TyvorFlightTimerMode::Auto;c.sensor=1;c.sensorId=s.id;c.instance=s.instance;c.modules=MODULE_TYPE_CROSSFIRE;c.verified=true;save(c);
 known(1);known(1,500);assert(!tyvorFlightTimerHasTime());known(0);known(1);known(1,250);assert(tyvorFlightTimerSeconds()==2);assert(homeData().arm==TyvorArmState::Armed);pass("explicitly verified raw 0/1 FC provider drives AUTO and independent ARM badge");
 known(0,50);tick(1000);assert(tyvorFlightTimerSeconds()==3);known(1);known(1);assert(tyvorFlightTimerSeconds()==1);pass("AUTO DISARM holds and confirmed re-ARM resets");
 telemetryStreaming=0;tick(500);assert(homeData().arm==TyvorArmState::Unknown);assert(tyvorFlightTimerSeconds()==1);known(1,500);assert(tyvorFlightTimerSeconds()==1);known(1);assert(tyvorFlightTimerSeconds()==2);pass("telemetry loss pauses; reconnect ARMED resumes without reset or gap time");
 g_tmr10ms+=193;telemetryStreaming=100;tyvorFlightTimerPoll();assert(tyvorFlightTimerArm()==TyvorArmState::Unknown);assert(tyvorFlightTimerSeconds()==2);known(1);known(1);assert(tyvorFlightTimerSeconds()==3);pass("stale ARM freezes while RF telemetry link remains alive");
 for(int v:{-1,2,255}){known(v);assert(tyvorFlightTimerArm()==TyvorArmState::Unknown);}pass("unsupported ARM numeric values stay UNKNOWN");
 fresh(1);s.unit=UNIT_VOLTS;tick(0);assert(tyvorFlightTimerArm()==TyvorArmState::Unknown);s.unit=UNIT_RAW;s.prec=1;assert(tyvorFlightTimerArm()==TyvorArmState::Unknown);s.prec=0;s.id=LINK_ID;assert(tyvorFlightTimerArm()==TyvorArmState::Unknown);s.id=c.sensorId;s.custom.ratio=1;assert(tyvorFlightTimerArm()==TyvorArmState::Unknown);s.custom.ratio=0;s.onlyPositive=1;assert(tyvorFlightTimerArm()==TyvorArmState::Unknown);s.onlyPositive=0;pass("wrong units/precision/transforms/known CRSF link sensors cannot authorize ARM");
 g_model.telemetrySensors[1]=s;assert(tyvorFlightTimerArm()==TyvorArmState::Unknown);memset(&g_model.telemetrySensors[1],0,sizeof(s));g_model.moduleData[1].type=MODULE_TYPE_CROSSFIRE;assert(tyvorFlightTimerArm()==TyvorArmState::Unknown);g_model.moduleData[1].type=MODULE_TYPE_NONE;pass("duplicate sensor identity or ambiguous module fails closed");
 c.verified=false;save(c);known(1);assert(!tyvorFlightTimerHasTime()&&homeData().arm==TyvorArmState::Unknown);pass("unverified sensor never starts AUTO or claims ARMED");
 assert(g_model.setUserData("TYVOR.FlightTimer.v1","bad"));tyvorFlightTimerModelLoaded();known(0);known(1);assert(!tyvorFlightTimerHasTime());pass("corrupt stored config defaults safely");
 printf("PASS %u actual-firmware integration cases; physical FC NOT VERIFIED\n",cases);return 0;
}
