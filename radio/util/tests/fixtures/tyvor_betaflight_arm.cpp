// Synthetic, CRC-valid FC packets against real firmware objects. Physical ARMED is NOT VERIFIED.
#include "edgetx.h"
#include "gui/128x64/tyvor_fc_arm.h"
#include "gui/128x64/tyvor_flight_timer.h"
#include "telemetry/crossfire.h"
#include "pulses/crossfire.h"
#include "hal/module_port.h"
#include "hal/switch_driver.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
extern TyvorFlightData homeData() asm("_ZL23readTyvorHomeFlightDatav");
extern void homeDraw() asm("_ZL13drawTyvorHomev");
extern void simuSetSwitch(uint8_t,int8_t);
extern void boardInitSwitches();
static uint8_t rx[TELEMETRY_RX_PACKET_SIZE],rxlen;
static std::string out;
static unsigned cases;
static void pass(const char* s){++cases;printf("PASS %s\n",s);fflush(stdout);}
static std::vector<uint8_t> frame(uint8_t id,std::vector<uint8_t> p){std::vector<uint8_t> f={RADIO_ADDRESS,uint8_t(p.size()+2),id};f.insert(f.end(),p.begin(),p.end());f.push_back(crc8(f.data()+2,f.size()-2));return f;}
static void send(const std::vector<uint8_t>& f){CrossfireDriver.processFrame(modulePortGetState(INTERNAL_MODULE),const_cast<uint8_t*>(f.data()),f.size(),rx,&rxlen);}
static void link(){send(frame(LINK_ID,{65,67,97,8,0,2,7,70,94,6}));}
static void mode(const char* s){send(frame(FLIGHT_MODE_ID,{s,s+strlen(s)+1}));}
static void state(TyvorArmState wanted){auto before=g_model;auto d=homeData();assert(d.arm==wanted);assert(!memcmp(&before,&g_model,sizeof(before)));}
static int fmIndex(){for(int i=0;i<MAX_TELEMETRY_SENSORS;i++)if(g_model.telemetrySensors[i].id==FLIGHT_MODE_ID&&g_model.telemetrySensors[i].isAvailable())return i;return -1;}
static void save(TyvorFcArmConfig c){char text[40];tyvorEncodeFcArmConfig(text,c);assert(g_model.setUserData("TYVOR.FcArm.v1",text));tyvorFcArmModelLoaded();}
static void dump(const char* name){
 for(auto item:{std::make_pair("sensors",std::make_pair((const void*)g_model.telemetrySensors,sizeof(g_model.telemetrySensors))),std::make_pair("items",std::make_pair((const void*)telemetryItems,sizeof(telemetryItems))),std::make_pair("stream",std::make_pair((const void*)&telemetryStreaming,sizeof(telemetryStreaming)))}){
  FILE* f=fopen((out+"/"+name+"-"+item.first+".bin").c_str(),"wb");assert(f);assert(fwrite(item.second.first,1,item.second.second,f)==item.second.second);fclose(f);
 }
 auto now=get_tmr10ms();FILE* f=fopen((out+"/"+name+"-clock.bin").c_str(),"wb");assert(f);assert(fwrite(&now,1,sizeof(now),f)==sizeof(now));fclose(f);
 lcdClear();homeDraw();f=fopen((out+"/"+name+"-oled.bin").c_str(),"wb");assert(f);assert(fwrite(displayBuf,1,1024,f)==1024);fclose(f);
}
extern "C" int __wrap_main(int,char**){
 out=getenv("TYVOR_BF455_TEST_OUTPUT");memset(&g_model,0,sizeof(g_model));memset(&g_eeGeneral,0,sizeof(g_eeGeneral));g_model.clearUserData();
 for(auto& item:telemetryItems)item.clear();g_model.moduleData[0].type=MODULE_TYPE_CROSSFIRE;modulePortInit();allowNewSensors=true;link();link();mode("AIR*");
 const int index=fmIndex();assert(index>=0);tyvorFcArmModelLoaded();state(TyvorArmState::Unknown);assert(!strcmp(tyvorFcArmStatusText(),"Set FC profile + Save"));pass("no profile: discovered AIR* does not opt every model into Betaflight");
 TyvorFcArmConfig c;c.profile=TyvorFcArmProfile::Betaflight455;c.sensor=index+1;c.modules=MODULE_TYPE_CROSSFIRE;save(c);state(TyvorArmState::Unknown);assert(!strcmp(tyvorFcArmStatusText(),"Verify FC + Save"));pass("profile requires explicit verified FC confirmation");
 c.verified=true;save(c);state(TyvorArmState::Disarmed);assert(!strcmp(tyvorFcArmStatusText(),"FC DISARMED"));dump("air-star");pass("confirmed BF4.5.5 actual CRC parser -> FM -> HOME DISARMED");
 for(const char* text:{"ACRO","RTH","MANU","STAB","HOR","AIR"}){mode(text);state(TyvorArmState::Armed);std::string d=std::string(text)+"*";mode(d.c_str());state(TyvorArmState::Disarmed);}
 mode("AIR");dump("air-armed-synthetic");mode("WAIT*");state(TyvorArmState::Disarmed);pass("whitelisted release modes with/without star; WAIT requires star; ARMED synthetic only");
 for(const char* text:{"AIR!","AIR?","!FS!","!FS!*","WAIT","ANGL","AIR**","AIR* ","BAD\nMODE","ARMED","DISARMED"}){mode(text);state(TyvorArmState::Unknown);}
 mode("AIR!");dump("unsupported-bang");mode("AIR?");dump("unsupported-question");mode("!FS!");dump("failsafe");pass("newer dialects, failsafe and malformed/unrecognized strings stay UNKNOWN");
 mode("AIR");g_tmr10ms+=193;link();state(TyvorArmState::Unknown);assert(!strcmp(tyvorFcArmStatusText(),"FM stale"));dump("stale");mode("AIR*");state(TyvorArmState::Disarmed);pass("FC age bound independent of active RF link; fresh packets recover");
 mode("AIR");for(int i=0;i<102;++i){++g_tmr10ms;telemetryInterrupt10ms();}state(TyvorArmState::Unknown);dump("lost");link();link();state(TyvorArmState::Unknown);mode("AIR*");state(TyvorArmState::Disarmed);dump("reconnected");pass("actual whole-link timeout, reconnect without fresh FC packet, fresh DISARM recovery");
 auto& s=g_model.telemetrySensors[index];auto original=s;
 s.unit=UNIT_RAW;state(TyvorArmState::Unknown);s=original;s.prec=1;state(TyvorArmState::Unknown);s=original;s.instance=1;state(TyvorArmState::Unknown);s=original;s.subId=1;state(TyvorArmState::Unknown);s=original;s.filter=1;state(TyvorArmState::Unknown);s=original;pass("wrong FM identity, units, precision and transforms rejected");
 int empty=availableTelemetryIndex();assert(empty>=0);g_model.telemetrySensors[empty]=s;state(TyvorArmState::Unknown);g_model.telemetrySensors[empty]={};
 g_model.moduleData[1].type=MODULE_TYPE_CROSSFIRE;state(TyvorArmState::Unknown);g_model.moduleData[1].type=MODULE_TYPE_NONE;pass("duplicate FM sensor and ambiguous RF module stay UNKNOWN");
 // The existing SWITCH clock and persisted timer key are never edited by FC presentation.
 switchInit();boardInitSwitches();g_eeGeneral.switchSetType(0,SWITCH_3POS);
 TyvorFlightTimerConfig timer;timer.mode=TyvorFlightTimerMode::Switch;timer.switchSource=SWSRC_FIRST_SWITCH+2;char timerText[64];tyvorEncodeFlightConfig(timerText,timer);assert(g_model.setUserData("TYVOR.FlightTimer.v1",timerText));tyvorFlightTimerModelLoaded();
 simuSetSwitch(0,-1);tyvorFlightTimerPoll();simuSetSwitch(0,1);tyvorFlightTimerPoll();g_tmr10ms+=200;mode("AIR*");tyvorFlightTimerPoll();assert(tyvorFlightTimerSeconds()==2);state(TyvorArmState::Disarmed);
 auto clock=tyvorFlightTimerSeconds();auto model=g_model;save(c);assert(tyvorFlightTimerSeconds()==clock&&!memcmp(&model,&g_model,sizeof(model)));assert(g_model.getUserData("TYVOR.FlightTimer.v1")->value==timerText);
 simuSetSwitch(0,-1);tyvorFlightTimerPoll();mode("AIR");g_tmr10ms+=100;tyvorFlightTimerPoll();assert(tyvorFlightTimerSeconds()==clock);state(TyvorArmState::Armed);pass("SWITCH ON may coexist with FC DISARM; SWITCH OFF with synthetic FC ARM; saving FC profile never resets timer/config");
 tyvorFcArmModelLoaded();mode("AIR*");state(TyvorArmState::Disarmed);pass("profile reload after model load/reboot preserves only explicit model configuration");
 g_model.clearUserData();tyvorFcArmModelLoaded();state(TyvorArmState::Unknown);assert(g_model.setUserData("TYVOR.FcArm.v1","1,9,1,5,1"));tyvorFcArmModelLoaded();state(TyvorArmState::Unknown);tyvorFcArmModelLoaded(false);state(TyvorArmState::Unknown);pass("other/unconfigured model, unsupported profile, corrupt config and failed model load stay UNKNOWN");
 printf("PASS %u integration cases; real DISARM evidence supplied by user; physical ARMED NOT VERIFIED\n",cases);return 0;
}
