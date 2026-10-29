// Test-only integration harness. Links existing native firmware objects unchanged.
#include "edgetx.h"
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
static std::string out;
static unsigned checks;
static uint8_t rx[TELEMETRY_RX_PACKET_SIZE], rxlen;
static void pass(const char* name) { ++checks; printf("PASS %s\n", name); fflush(stdout); }
static void dump(const char* name) {
  std::string prefix=out+"/"+name;
  for (auto entry: {std::make_pair("sensors",std::make_pair((const void*)g_model.telemetrySensors,sizeof(g_model.telemetrySensors))),
                    std::make_pair("items",std::make_pair((const void*)telemetryItems,sizeof(telemetryItems))),
                    std::make_pair("stream",std::make_pair((const void*)&telemetryStreaming,sizeof(telemetryStreaming)))}) {
    FILE* f=fopen((prefix+"-"+entry.first+".bin").c_str(),"wb");assert(f);
    assert(fwrite(entry.second.first,1,entry.second.second,f)==entry.second.second);fclose(f);
  }
  FILE* clock=fopen((prefix+"-clock.bin").c_str(),"wb");assert(clock);auto tick=get_tmr10ms();assert(fwrite(&tick,1,sizeof(tick),clock)==sizeof(tick));fclose(clock);
  FILE* f=fopen((prefix+".json").c_str(),"w");assert(f);
  auto d=homeData();
  fprintf(f,"{\"batteryValid\":%d,\"voltage_dV\":%u,\"percentValid\":%d,\"percent\":%u,\"gpsValid\":%d,\"satellites\":%u,\"powerValid\":%d,\"power\":%ld,\"powerDbm\":%d,\"modeValid\":%d,\"mode\":\"%s\",\"arm\":\"%s\"}\n",d.batteryValid,d.batteryDecivolts,d.batteryPercentValid,d.batteryPercent,d.satellitesValid,d.satellites,d.powerValid,(long)d.power,d.powerDbm,d.modeValid,d.mode,tyvorArmLabel(d.arm));fclose(f);
}
static std::vector<uint8_t> frame(uint8_t id,std::vector<uint8_t> payload) {
  std::vector<uint8_t> f={RADIO_ADDRESS,uint8_t(payload.size()+2),id};f.insert(f.end(),payload.begin(),payload.end());
  f.push_back(crc8(f.data()+2,f.size()-2));return f;
}
static void bytes(std::vector<uint8_t> f) {
  CrossfireDriver.processFrame(modulePortGetState(INTERNAL_MODULE),f.data(),f.size(),rx,&rxlen);
}
static void link(uint8_t lq=97) {bytes(frame(LINK_ID,{65,67,lq,8,0,2,7,70,94,6}));}
static void battery(int v=152,uint8_t percent=80) {bytes(frame(BATTERY_ID,{uint8_t(v>>8),uint8_t(v),0,12,0,0,50,percent}));}
static void gps(uint8_t sats=12) {bytes(frame(GPS_ID,{0,0,0,0,0,0,0,0,0,0,0,0,3,232,sats}));}
static void mode(const char* text="ANGLE") {std::vector<uint8_t> p(text,text+strlen(text)+1);bytes(frame(FLIGHT_MODE_ID,p));}
static int find(uint16_t id,uint8_t inst) {
 for(int i=0;i<MAX_TELEMETRY_SENSORS;i++) if(g_model.telemetrySensors[i].isAvailable() && g_model.telemetrySensors[i].id==id &&g_model.telemetrySensors[i].instance==inst)return i;
 return -1;
}
static TyvorFlightData readOnly() {
 auto before=g_model;TelemetryItem items[MAX_TELEMETRY_SENSORS];memcpy(items,telemetryItems,sizeof(items));
 auto d=homeData();assert(!memcmp(&g_model,&before,sizeof(before)));assert(!memcmp(items,telemetryItems,sizeof(items)));return d;
}
static void valid() {
 auto d=readOnly();assert(d.batteryValid&&d.batteryDecivolts==152&&d.batteryPercentValid&&d.batteryPercent==80);
 assert(d.satellitesValid&&d.satellites==12&&d.modeValid&&!strcmp(d.mode,"ANGLE"));
 assert(d.powerValid&&!d.powerDbm&&d.power==250&&d.arm==TyvorArmState::Unknown);
}
extern "C" int __wrap_main(int,char**) {
 const char* path=getenv("TYVOR_CRSF_AUDIT_OUT");assert(path);out=path;
 memset(&g_model,0,sizeof(g_model));memset(&g_eeGeneral,0,sizeof(g_eeGeneral));
 for(auto &it:telemetryItems)it.clear();g_model.moduleData[INTERNAL_MODULE].type=MODULE_TYPE_CROSSFIRE;
 allowNewSensors=false;telemetryStreaming=0;modulePortInit();
 link();link();battery();gps();mode();assert(find(BATTERY_ID,0)<0);assert(!readOnly().batteryValid);dump("discovery-off");pass("CRSF packets without Discover do not populate HOME sensors");
 allowNewSensors=true;link();link();battery();gps();mode();valid();dump("valid");pass("actual CRC parser -> discovery -> sensor IDs/units/values -> HOME");
 int b=find(BATTERY_ID,0),p=find(BATTERY_ID,3),g=find(GPS_ID,5),m=find(FLIGHT_MODE_ID,0),tx=find(LINK_ID,6),lq=find(LINK_ID,2);
 assert(b>=0&&p>=0&&g>=0&&m>=0&&tx>=0&&lq>=0);
 assert(g_model.telemetrySensors[b].unit==UNIT_VOLTS&&g_model.telemetrySensors[b].prec==1);
 assert(g_model.telemetrySensors[p].unit==UNIT_PERCENT&&telemetryItems[lq].value==97&&g_model.telemetrySensors[lq].unit==UNIT_PERCENT);
 pass("discovered RxBt/Bat%/Sats/FM/TPWR/RQly identity and units");
 FILE* ids=fopen((out+"/sensor-map.tsv").c_str(),"w");assert(ids);
 for(int i=0;i<MAX_TELEMETRY_SENSORS;i++){const auto&s=g_model.telemetrySensors[i];if(s.isAvailable())fprintf(ids,"%d\t%.*s\t0x%04x\t%u\t%u\t%u\t%ld\t%d\n",i,int(sizeof(s.label)),s.label,s.id,s.instance,s.unit,s.prec,(long)telemetryItems[i].value,telemetryItems[i].timeout);}fclose(ids);
 auto corrupt=frame(BATTERY_ID,{0,168,0,12,0,0,50,90});corrupt.back()^=1;rxlen=0;bytes(corrupt);assert(telemetryItems[b].value==152);rxlen=0;pass("invalid CRC rejected before sensor update");
 auto split=frame(BATTERY_ID,{0,148,0,12,0,0,50,70});bytes({split.begin(),split.begin()+5});assert(rxlen==5&&telemetryItems[b].value==152);bytes({split.begin()+5,split.end()});assert(rxlen==0&&homeData().batteryDecivolts==148);battery();pass("fragmented UART frame reassembly");
 allowNewSensors=false;battery(146,60);assert(homeData().batteryDecivolts==146&&homeData().batteryPercent==60);battery();valid();pass("saved sensors update while discovery disabled");
 auto unit=g_model.telemetrySensors[b].unit;g_model.telemetrySensors[b].unit=UNIT_RAW;assert(!readOnly().batteryValid);dump("wrong-unit");g_model.telemetrySensors[b].unit=unit;pass("wrong voltage unit rejected");
 auto gp=g_model.telemetrySensors[g].prec;g_model.telemetrySensors[g].prec=1;assert(!readOnly().satellitesValid);g_model.telemetrySensors[g].prec=gp;pass("satellite precision mismatch rejected");
 battery(152,255);assert(homeData().batteryValid&&!homeData().batteryPercentValid&&tyvorDroneBatteryBars(homeData())==-1);dump("unsupported-percent");battery();pass("unsupported FC battery percentage has unknown bars");
 battery(32,5);assert(homeData().batteryDecivolts==32&&tyvorDroneBatteryBars(homeData())==1);dump("low-battery");battery();pass("low battery uses reported voltage and percent only");
 int empty=availableTelemetryIndex();assert(empty>=0);g_model.telemetrySensors[empty]=g_model.telemetrySensors[b];telemetryItems[empty]=telemetryItems[b];assert(!readOnly().batteryValid);g_model.telemetrySensors[empty]={};telemetryItems[empty].clear();pass("duplicate eligible sensor is ambiguous");
 telemetryItems[b].timeout=93;telemetryItems[g].timeout=93;telemetryItems[tx].timeout=93;telemetryItems[p].timeout=93;telemetryItems[m].timeout=112;
 auto d=readOnly();assert(!d.batteryValid&&!d.satellitesValid&&!d.powerValid&&!d.modeValid);dump("stale");pass("per-sensor timeout independent of active link");
 link();battery();gps();mode();valid();pass("fresh packets recover stale HOME values");
 for(int i=0;i<102;i++)telemetryInterrupt10ms();assert(!TELEMETRY_STREAMING());d=readOnly();assert(!d.batteryValid&&!d.satellitesValid&&!d.powerValid&&!d.modeValid);dump("lost");pass("actual 10 ms timer expires whole telemetry link");
 link();link();assert(!readOnly().batteryValid&&!readOnly().modeValid);dump("link-only");pass("link reconnect does not resurrect stale FC data");
 battery();gps();mode();valid();dump("reconnected");pass("FC telemetry recovers only upon new packets");
 bytes(frame(FLIGHT_MODE_ID,{'A','R','M','E','D',0}));d=readOnly();assert(d.modeValid&&d.arm==TyvorArmState::Unknown);pass("FC flight-mode text is not ARM confirmation");
 mode();g_model.moduleData[INTERNAL_MODULE].type=MODULE_TYPE_NONE;assert(!readOnly().batteryValid);g_model.moduleData[INTERNAL_MODULE].type=MODULE_TYPE_CROSSFIRE;pass("non-CRSF module cannot lend CRSF semantics");
 // Existing parser maps wire 0x1C ground power to sensor 0x1D instance 1;
 // wire 0x1D receiver power to sensor 0x1C instance 1. Verify, do not relabel.
 allowNewSensors=true;bytes(frame(LINK_RX_ID,{60,90,96,6,24}));bytes(frame(LINK_TX_ID,{65,88,95,5,10,25}));
 int ground=find(LINK_TX_ID,1),air=find(LINK_RX_ID,1);assert(ground>=0&&air>=0&&telemetryItems[ground].value==24&&telemetryItems[air].value==10);
 telemetryItems[tx].setOld();d=readOnly();assert(d.powerValid&&d.powerDbm&&d.power==24);dump("tx-dbm");pass("ground TX power fallback verified against actual RX/TX parser mapping");
 telemetryItems[ground].setOld();assert(!readOnly().powerValid);dump("rx-power-only");pass("receiver RF power cannot masquerade as ground TX power");
 battery();gps();mode();link();
 for(int i=0;i<600;i++){++g_tmr10ms;link();telemetryInterrupt10ms();}
 auto cadence=readOnly();
 printf("CONTINUOUS_LINK_AFTER_6000MS timeout_battery=%d batteryValid=%d modeValid=%d\n",telemetryItems[b].timeout,cadence.batteryValid,cadence.modeValid);fflush(stdout);
 assert(!cadence.batteryValid&&!cadence.modeValid&&!cadence.satellitesValid);
 dump("fc-stale-rf-active");
 pass("continued RF link cannot keep missing FC packets fresh forever");
 for(int period: {1,2,3,5,10,32}) {
  link();link();battery();gps();mode();
  for(int i=0;i<600;i++){++g_tmr10ms;if(i%period==0)link();telemetryInterrupt10ms();}
  auto aged=readOnly();assert(!aged.batteryValid&&!aged.modeValid&&!aged.satellitesValid);
 }
 pass("FC sensor expiry is bounded across six RF link packet cadences");
 // Actual receive metadata handles the unsigned 32-bit tick wrap.
 g_tmr10ms=UINT32_MAX-10;link();link();battery();gps();mode();g_tmr10ms=5;
 assert(readOnly().batteryValid&&readOnly().modeValid);
 g_tmr10ms=500;assert(!readOnly().batteryValid&&!readOnly().modeValid);
 pass("real receive timestamps handle tick wrap without extending stale data");

 FILE* report=fopen((out+"/pipeline-result.json").c_str(),"w");assert(report);fprintf(report,"{\"result\":\"PASS\",\"cases\":%u,\"test_preserves_original_native_objects\":true,\"physical_telemetry\":\"NOT VERIFIED\"}\n",checks);fclose(report);
 return 0;
}
