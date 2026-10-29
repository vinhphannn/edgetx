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

static void rf(unsigned lq,unsigned tq=100){send(frame(LINK_ID,{65,67,uint8_t(lq),8,0,2,1,70,uint8_t(tq),6}));}
static bool pixel(int x,int y){return displayBuf[(y/8)*128+x]&(1<<(y%8));}
static std::vector<bool> modePixels(){std::vector<bool> out;for(int y=37;y<43;y++)for(int x=30;x<125;x++)out.push_back(pixel(x,y));return out;}
static void renderedMode(const char* raw,const char* wanted){
 mode(raw);auto d=homeData();assert(d.modeValid&&!strcmp(d.mode,raw));const int index=fmIndex();auto original=telemetryItems[index];
 lcdClear();lcdDrawText(30,37,wanted,SMLSIZE);auto expected=modePixels();lcdClear();homeDraw();assert(modePixels()==expected);assert(!memcmp(&original,&telemetryItems[index],sizeof(original)));
}
extern "C" int __wrap_main(int,char**){
 out=getenv("TYVOR_HOME_RF_TEST_OUTPUT");memset(&g_model,0,sizeof(g_model));memset(&g_eeGeneral,0,sizeof(g_eeGeneral));g_model.clearUserData();for(auto&i:telemetryItems)i.clear();g_model.moduleData[0].type=MODULE_TYPE_CROSSFIRE;modulePortInit();allowNewSensors=true;rf(100);rf(100);mode("STAB*");
 int fm=fmIndex();assert(fm>=0);tyvorFcArmModelLoaded();state(TyvorArmState::Unknown);assert(!strcmp(tyvorFcArmStatusText(),"Set FC profile + Save"));pass("real screenshot state reproduced: STAB* without saved FC profile stays UNKNOWN");
 TyvorFcArmConfig c;c.profile=TyvorFcArmProfile::Betaflight455;c.sensor=fm+1;c.modules=MODULE_TYPE_CROSSFIRE;c.verified=true;save(c);state(TyvorArmState::Disarmed);
 for(auto pair:{std::make_pair("STAB*","STAB"),std::make_pair("AIR*","AIR"),std::make_pair("AIR!","AIR!"),std::make_pair("AIR?","AIR?"),std::make_pair("!FS!","!FS!"),std::make_pair("!FS!*","!FS!")})renderedMode(pair.first,pair.second);
 mode("STAB*");state(TyvorArmState::Disarmed);dump("stab-disarmed");pass("HOME mode removes only terminal star while original sensor and ARM input retain it");
 int lqIndex=-1;for(int i=0;i<MAX_TELEMETRY_SENSORS;++i)if(g_model.telemetrySensors[i].id==LINK_ID&&g_model.telemetrySensors[i].instance==2)lqIndex=i;assert(lqIndex>=0);
 for(unsigned q:{25u,50u,75u,100u}){
  rf(q,0);mode("STAB*");auto d=homeData();assert(d.linkQualityValid&&d.linkQuality==q&&d.powerValid&&d.power==10);int bars=tyvorHomeLinkBars(d);lcdClear();homeDraw();
  for(int i=0;i<5;i++){int count=0;for(int y=17;y<23;y++)for(int x=46+4*i;x<49+4*i;x++)count+=pixel(x,y);assert(count==(i<bars?3*(i+2):0));}
  dump(("lq-"+std::to_string(q)).c_str());
 }
 pass("actual CRSF RQly instance2 drives 25/50/75/100 bars; TQly0 and fixed 10mW cannot drive indicator");
 rf(0);auto d=homeData();assert(!TELEMETRY_STREAMING()&&!d.linkQualityValid&&tyvorHomeLinkBars(d)==-1);dump("lq-zero-link-lost");pass("wire RQly0 follows existing EdgeTX link-loss policy and shows UNKNOWN, not frozen bars");
 // Explicit synthetic valid-zero presentation fixture, distinct from parser link-loss semantics.
 telemetryStreaming=100;telemetryItems[lqIndex].setFresh();d=homeData();assert(d.linkQualityValid&&d.linkQuality==0&&tyvorHomeLinkBars(d)==0);dump("lq-0-valid-projection");pass("valid-zero projection renders zero columns; fixture streaming flag is synthetic");
 rf(100);mode("STAB*");g_tmr10ms+=101;telemetryStreaming=100;telemetryItems[fm].setFresh();d=homeData();assert(!d.linkQualityValid&&d.modeValid&&d.arm==TyvorArmState::Disarmed);dump("lq-stale");pass("stale RQly rejected independently of fresh FC FM and active streaming flag");
 rf(50);auto& s=g_model.telemetrySensors[lqIndex];auto saved=s;s.unit=UNIT_RAW;assert(!homeData().linkQualityValid);s=saved;s.prec=1;assert(!homeData().linkQualityValid);s=saved;int free=availableTelemetryIndex();assert(free>=0);g_model.telemetrySensors[free]=s;telemetryItems[free]=telemetryItems[lqIndex];assert(!homeData().linkQualityValid);g_model.telemetrySensors[free]={};pass("wrong LQ unit/precision or duplicate identity produces unknown");
 rf(75);mode("STAB*");telemetryStreaming=0;assert(!homeData().linkQualityValid);state(TyvorArmState::Unknown);dump("lost");rf(75);mode("STAB*");state(TyvorArmState::Disarmed);dump("reconnected");pass("loss and fresh reconnect update RF icon and FC status without using a switch");
 printf("PASS %u actual HOME integration groups; physical saved FC configuration NOT VERIFIED\n",cases);return 0;
}
