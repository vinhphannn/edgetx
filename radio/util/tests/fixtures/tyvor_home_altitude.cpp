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


static void rf(){send(frame(LINK_ID,{65,67,75,8,0,2,1,70,100,6}));}
static void gps(unsigned sats,int altitude=125){unsigned wire=altitude+1000;send(frame(GPS_ID,{0,0,0,0,0,0,0,0,0,0,0,0,uint8_t(wire>>8),uint8_t(wire),uint8_t(sats)}));}
static void packedAlt(unsigned packed){send(frame(BARO_ALT_ID,{uint8_t(packed>>8),uint8_t(packed)}));}
static void alt(int meters){assert(meters>=-1000&&meters<=32766);unsigned packed=meters<=2276?unsigned(meters*10+10000):(0x8000u|unsigned(meters));packedAlt(packed);}
static int find(uint16_t id,unsigned instance){for(int i=0;i<MAX_TELEMETRY_SENSORS;++i)if(g_model.telemetrySensors[i].isAvailable()&&g_model.telemetrySensors[i].id==id&&g_model.telemetrySensors[i].instance==instance)return i;return -1;}
static std::vector<bool> pixels(int x0,int x1){std::vector<bool> p;for(int y=55;y<63;++y)for(int x=x0;x<x1;++x)p.push_back(displayBuf[(y/8)*128+x]&(1<<(y%8)));return p;}
static void rendered(const char* sats,const char* altitude){
 auto model=g_model;TelemetryItem items[MAX_TELEMETRY_SENSORS];memcpy(items,telemetryItems,sizeof(items));
 lcdClear();lcdDrawText(48,55,sats,getTextWidth(sats)<=35?0:SMLSIZE);auto sp=pixels(48,83);
 lcdClear();lcdDrawText(90,55,altitude,getTextWidth(altitude)<=35?0:SMLSIZE);auto ap=pixels(90,127);
 lcdClear();homeDraw();assert(pixels(48,83)==sp&&pixels(90,127)==ap);
 assert(!memcmp(&model,&g_model,sizeof(model))&&!memcmp(items,telemetryItems,sizeof(items)));
}
extern "C" int __wrap_main(int,char**){
 out=getenv("TYVOR_ALT_TEST_OUTPUT");memset(&g_model,0,sizeof(g_model));memset(&g_eeGeneral,0,sizeof(g_eeGeneral));g_model.clearUserData();for(auto&i:telemetryItems)i.clear();g_model.moduleData[0].type=MODULE_TYPE_CROSSFIRE;modulePortInit();allowNewSensors=true;rf();rf();mode("STAB*");
 TyvorFcArmConfig c;c.profile=TyvorFcArmProfile::Betaflight455;c.sensor=fmIndex()+1;c.modules=MODULE_TYPE_CROSSFIRE;c.verified=true;save(c);
 auto d=homeData();assert(!d.satellitesValid&&!d.altitudeValid&&d.powerValid&&d.power==10);rendered("--","--");dump("missing");pass("missing SATS/ALT stays -- even though TX power is valid10mW");
 gps(12,125);d=homeData();assert(d.satellitesValid&&d.satellites==12&&!d.altitudeValid);rendered("12","--");dump("gps-only");pass("0x02 GAlt is not silently relabelled relative or absolute for BF4.5.5");
 for(int sats:{0,8,12,18})for(int height:{0,12,-3,125}){
  rf();mode("STAB*");gps(sats);alt(height);d=homeData();assert(d.satellitesValid&&d.satellites==sats&&d.altitudeValid&&d.altitudeMeters==height&&d.arm==TyvorArmState::Disarmed&&d.linkQualityValid&&d.linkQuality==75);
  char sc[16],ac[16];snprintf(sc,sizeof(sc),"%d",sats);snprintf(ac,sizeof(ac),"%dm",height);rendered(sc,ac);dump(("sats-"+std::to_string(sats)+"-alt-"+std::to_string(height)).c_str());
 }
 pass("CRC parser -> IDs/instances -> zero-inclusive SATS and signed relative altitude -> exact HOME pixels");
 int s=find(GPS_ID,5),a=find(BARO_ALT_ID,0),g=find(GPS_ID,4);assert(s>=0&&a>=0&&g>=0);
 assert(g_model.telemetrySensors[s].unit==UNIT_RAW&&!g_model.telemetrySensors[s].prec);assert(g_model.telemetrySensors[a].unit==UNIT_METERS&&g_model.telemetrySensors[a].prec==2);
 alt(-3);assert(telemetryItems[a].value==-300&&homeData().altitudeMeters==-3);pass("0x09 wire offset decoded once by parser; UNIT_METERS precision2 is cm, no second zero/offset");
 for(int high:{-1000,32766}){rf();alt(high);d=homeData();assert(d.altitudeValid&&d.altitudeMeters==high);char text[16];snprintf(text,sizeof(text),"%dm",high);rendered("18",text);dump(high<0?"alt-min":"alt-max");}
 packedAlt(0xffff);assert(!homeData().altitudeValid);rendered("18","--");dump("invalid-sentinel");pass("protocol limits fit metric cell; reserved0xffff and numeric overflow rejected");
 auto savedAlt=g_model.telemetrySensors[a];auto savedSats=g_model.telemetrySensors[s];
 alt(12);g_model.telemetrySensors[a].unit=UNIT_FEET;assert(!homeData().altitudeValid);g_model.telemetrySensors[a]=savedAlt;
 g_model.telemetrySensors[a].autoOffset=1;assert(!homeData().altitudeValid);g_model.telemetrySensors[a]=savedAlt;
 g_model.telemetrySensors[a].custom.offset=100;assert(!homeData().altitudeValid);g_model.telemetrySensors[a]=savedAlt;
 g_model.telemetrySensors[a].custom.ratio=255;assert(!homeData().altitudeValid);g_model.telemetrySensors[a]=savedAlt;
 g_model.telemetrySensors[s].unit=UNIT_PERCENT;assert(!homeData().satellitesValid);g_model.telemetrySensors[s]=savedSats;
 g_model.telemetrySensors[s].custom.offset=1;assert(!homeData().satellitesValid);g_model.telemetrySensors[s]=savedSats;
 g_model.telemetrySensors[s].prec=1;assert(!homeData().satellitesValid);g_model.telemetrySensors[s]=savedSats;pass("wrong units/precision and radio-side transforms cannot fake FC altitude or satellite count");
 g_model.telemetrySensors[a].unit=UNIT_FEET;dump("wrong-unit");g_model.telemetrySensors[a]=savedAlt;
 int free=availableTelemetryIndex();assert(free>=0);g_model.telemetrySensors[free]=savedAlt;telemetryItems[free]=telemetryItems[a];assert(!homeData().altitudeValid);g_model.telemetrySensors[free]={};g_model.telemetrySensors[free]=savedSats;telemetryItems[free]=telemetryItems[s];assert(!homeData().satellitesValid);g_model.telemetrySensors[free]={};pass("duplicate eligible sources do not choose arbitrary values");
 rf();gps(12);alt(12);g_tmr10ms+=193;rf();mode("STAB*");gps(12);assert(!homeData().altitudeValid&&homeData().satellitesValid);rendered("12","--");dump("alt-stale");
 alt(12);g_tmr10ms+=497;rf();mode("STAB*");alt(12);assert(homeData().altitudeValid&&!homeData().satellitesValid);rendered("--","12m");dump("sats-stale");pass("monotonic ALT1.92s/SATS4.96s freshness expires independently of RF/other sensor traffic");
 gps(12);alt(-3);for(int i=0;i<102;++i){++g_tmr10ms;telemetryInterrupt10ms();}assert(!homeData().altitudeValid&&!homeData().satellitesValid);dump("lost");rf();rf();assert(!homeData().altitudeValid&&!homeData().satellitesValid);dump("link-only");gps(8);alt(125);mode("STAB*");assert(homeData().altitudeValid&&homeData().satellitesValid);rendered("8","125m");dump("reconnected");pass("whole-link loss/reconnect requires fresh FC samples, never falls back to power");
 printf("PASS %u SATS/ALT integration groups; real relative-altitude sender NOT VERIFIED\n",cases);return 0;
}
