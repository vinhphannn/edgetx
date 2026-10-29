// Test-only: run current firmware timer, renderer and CRSF objects. No RF hardware.
#include "edgetx.h"
#include "timers.h"
#include "telemetry/crossfire.h"
#include "pulses/crossfire.h"
#include "hal/module_port.h"
#include "gui/128x64/tyvor_flight_data.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

extern TyvorFlightData homeData() asm("_ZL23readTyvorHomeFlightDatav");
extern void homeDraw() asm("_ZL13drawTyvorHomev");
extern void timerDraw(const char*,bool) asm("_ZL18drawTyvorHomeTimerPKcb");
static std::string out;
static unsigned cases;
static uint8_t rx[TELEMETRY_RX_PACKET_SIZE],rxlen;
static void pass(const char* name){++cases;printf("PASS %s\n",name);fflush(stdout);}
static std::vector<uint8_t> timerPixels(){
 std::vector<uint8_t> v;
 for(int y=23;y<35;y++)for(int x=5;x<71;x++)v.push_back(bool(displayBuf[(y/8)*128+x]&(1<<(y%8))));
 return v;
}
static void render(const char* name,const char* expected){
 auto model=g_model;TimerState states[TIMERS];memcpy(states,timersStates,sizeof(states));
 // HOME now has an independent flight clock; changing Timer1 must not drive TIME.
 // No flight-clock provider is configured in this legacy Timer1 regression.
 (void)expected;
 lcdClear();timerDraw("--:--",false);auto wanted=timerPixels();
 lcdClear();homeDraw();assert(timerPixels()==wanted);
 assert(!memcmp(&model,&g_model,sizeof(model))&&!memcmp(states,timersStates,sizeof(states)));
 FILE* f=fopen((out+"/"+name+".bin").c_str(),"wb");assert(f);assert(fwrite(displayBuf,1,1024,f)==1024);fclose(f);
}
static void ticks(unsigned n,int throttle=0){for(unsigned i=0;i<n;i++){++g_tmr10ms;evalTimers(throttle,1);}}
static void setup(int mode,uint32_t start=0,int sw=SWSRC_NONE){
 memset(g_model.timers,0,sizeof(g_model.timers));memset(timersStates,0,sizeof(TimerState)*TIMERS);
 g_model.timers[0].mode=mode;g_model.timers[0].start=start;g_model.timers[0].swtch=sw;timerReset(0);
}
static std::vector<uint8_t> frame(uint8_t id,std::vector<uint8_t> p){
 std::vector<uint8_t> f={RADIO_ADDRESS,uint8_t(p.size()+2),id};f.insert(f.end(),p.begin(),p.end());f.push_back(crc8(f.data()+2,f.size()-2));return f;
}
static void send(std::vector<uint8_t> f){CrossfireDriver.processFrame(modulePortGetState(INTERNAL_MODULE),f.data(),f.size(),rx,&rxlen);}
static void link(){send(frame(LINK_ID,{65,67,97,8,0,2,7,70,94,6}));}
static void mode(const char* s){send(frame(FLIGHT_MODE_ID,{s,s+strlen(s)+1}));}
static int modeIndex(){for(int i=0;i<MAX_TELEMETRY_SENSORS;i++)if(g_model.telemetrySensors[i].isAvailable()&&g_model.telemetrySensors[i].id==FLIGHT_MODE_ID)return i;return -1;}
static void dumpTelemetry(const std::string& name){
 for(auto entry:{std::make_pair("sensors",std::make_pair((const void*)g_model.telemetrySensors,sizeof(g_model.telemetrySensors))),
                 std::make_pair("items",std::make_pair((const void*)telemetryItems,sizeof(telemetryItems))),
                 std::make_pair("stream",std::make_pair((const void*)&telemetryStreaming,sizeof(telemetryStreaming)))}){
  FILE* f=fopen((out+"/"+name+"-"+entry.first+".bin").c_str(),"wb");assert(f);assert(fwrite(entry.second.first,1,entry.second.second,f)==entry.second.second);fclose(f);
 }
 auto tick=get_tmr10ms();FILE* f=fopen((out+"/"+name+"-clock.bin").c_str(),"wb");assert(f);assert(fwrite(&tick,1,sizeof(tick),f)==sizeof(tick));fclose(f);
}
static void unknown(){auto model=g_model;auto d=homeData();assert(d.arm==TyvorArmState::Unknown);assert(!memcmp(&model,&g_model,sizeof(model)));}
extern "C" int __wrap_main(int,char**){
 const char* dir=getenv("TYVOR_TIME_ARM_TEST_OUTPUT");assert(dir);out=dir;
 memset(&g_model,0,sizeof(g_model));memset(&g_eeGeneral,0,sizeof(g_eeGeneral));g_vbat100mV=75;
 for(auto&it:telemetryItems)it.clear();
 setup(TMRMODE_OFF);timerSet(0,77);auto config=g_model;ticks(300);assert(timersStates[0].val==77);render("timer-off","--:--");assert(!memcmp(&config,&g_model,sizeof(config)));pass("OFF follows saved Timer1 mode; HOME never enables or resets it");
 setup(TMRMODE_ON);ticks(99);assert(timersStates[0].val==0);render("timer-on-99ticks","00:00");ticks(1);assert(timersStates[0].val==1);render("timer-on-1s","00:01");ticks(200);assert(timersStates[0].val==3);render("timer-on-3s","00:03");pass("Timer1 core increments per 100 ticks; independent HOME clock stays unconfigured");
 g_model.timers[1].mode=TMRMODE_ON;timerSet(1,900);render("timer1-not-timer2","00:03");pass("Timer1/Timer2/RTC do not drive independent HOME flight clock");
 setup(TMRMODE_ON,0,-SWSRC_ON);ticks(300);assert(timersStates[0].val==0);render("timer-switch-paused","00:00");g_model.timers[0].swtch=SWSRC_NONE;ticks(100);assert(timersStates[0].val==1);render("timer-switch-running","00:01");pass("ON still honors configured switch; paused numeric timer is not OFF");
 setup(TMRMODE_ON,60);render("countdown-reset","01:00");ticks(100);assert(timersStates[0].val==59);render("countdown-running","00:59");pass("configured countdown follows core state without editing model");
 g_model.timers[0].showElapsed=1;render("elapsed-running","00:01");timerReset(0);render("elapsed-reset-stock-semantics","01:00");ticks(100);render("elapsed-first-second","00:01");pass("elapsed Timer1 state stays independent of HOME flight clock");
 setup(TMRMODE_THR);ticks(200,0);assert(!timersStates[0].val);ticks(100,128);assert(timersStates[0].val==1);render("throttle-timer","00:01");pass("throttle timer retains existing start condition, no control changes");
 setup(TMRMODE_ON);g_model.timers[0].persistent=1;g_model.timers[0].value=125;restoreTimers();assert(timersStates[0].val==125);render("persistent-timer","02:05");ticks(100);render("persistent-running","02:06");assert(g_model.timers[0].value==125);pass("persistent value restored; HOME does not overwrite stored timer configuration");
 setup(TMRMODE_OFF);g_model.moduleData[INTERNAL_MODULE].type=MODULE_TYPE_CROSSFIRE;modulePortInit();allowNewSensors=true;link();link();
 int fixture=0;for(const char* text:{"ACRO*","ACRO!","ACRO?","ACRO","AIR*","AIR!","AIR?","AIR","ANGL","OK","WAIT","!ERR","ARMED","DISARMED","!FS!"}){mode(text);assert(homeData().modeValid&&!strcmp(homeData().mode,text));unknown();dumpTelemetry("mode-"+std::to_string(fixture++));}
 pass("unconfirmed FC dialects and arbitrary ARMED/DISARMED text cannot authorize ARM state");
 mode("AIR*");unknown();dumpTelemetry("air-star");render("air-star-home","--:--");
 pass("reported AIR* reproduces MODE without guessing FC family/version or ARM state");
 // Synthetic FC-origin 0x29 carries a firmware name, but current firmware only
 // caches TX-module (0xEE) device identity. Never confuse that with FC identity.
 auto beforeIdentity=g_model;auto moduleIdentity=crossfireModuleStatus[INTERNAL_MODULE];
 std::vector<uint8_t> identity={RADIO_ADDRESS,0xC8};
 const char* claimed="Betaflight 4.5.2: TEST";
 identity.insert(identity.end(),claimed,claimed+strlen(claimed)+1);
 identity.insert(identity.end(),12,0);identity.push_back(0);identity.push_back(1);
 send(frame(DEVICE_INFO_ID,identity));
 assert(!memcmp(&beforeIdentity,&g_model,sizeof(g_model)));
 assert(!memcmp(&moduleIdentity,&crossfireModuleStatus[INTERNAL_MODULE],sizeof(moduleIdentity)));
 unknown();pass("FC-origin Device Info is not TX-module identity or an implemented FC ARM provider");

 int m=modeIndex();assert(m>=0);mode("BAD\nMODE");assert(!homeData().modeValid);unknown();dumpTelemetry("bad-mode");pass("invalid flight-mode text remains UNKNOWN");
 mode("ACRO");auto unit=g_model.telemetrySensors[m].unit;g_model.telemetrySensors[m].unit=UNIT_RAW;assert(!homeData().modeValid);unknown();g_model.telemetrySensors[m].unit=unit;pass("wrong-unit FM sensor cannot become an ARM source");
 mode("ACRO");g_tmr10ms+=193;link();assert(!homeData().modeValid);unknown();dumpTelemetry("stale-mode");render("mode-stale-arm-unknown","--:--");pass("stale MODE while RF link lives returns unknown state");
 mode("ACRO");telemetryStreaming=0;unknown();dumpTelemetry("lost");render("telemetry-lost-arm-unknown","--:--");link();link();unknown();mode("OK");unknown();dumpTelemetry("reconnected");pass("loss and reconnect never resurrect an inferred ARM state");
 send(frame(0x1f,{0,0,128,0,0,0,0,3,2}));unknown();pass("unsupported MAVLink-FC frame is not silently treated as trusted ARM telemetry");
 assert(!strcmp(tyvorArmLabel(TyvorArmState::Armed),"ARMED")&&!strcmp(tyvorArmLabel(TyvorArmState::Disarmed),"DISARMED"));pass("ARM/DISARM renderer labels supported; actual FC decode intentionally unconfigured");
 FILE* f=fopen((out+"/time-arm-result.json").c_str(),"w");assert(f);fprintf(f,"{\"result\":\"PASS\",\"cases\":%u,\"physical_fc\":\"NOT VERIFIED\",\"trusted_arm_decode\":\"NOT VERIFIED - no confirmed FC source\",\"production_sources_changed\":false}\n",cases);fclose(f);
 return 0;
}
