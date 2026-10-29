"""Execute the read-only HOME telemetry reader with valid/stale/ambiguous data."""
from pathlib import Path
import shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]


@unittest.skipUnless(shutil.which('g++'),'requires host g++')
class TyvorFlightDataTests(unittest.TestCase):
    def test_reader_validity_units_no_inferred_arm_and_read_only(self):
        source=(ROOT/'radio/src/gui/128x64/view_main.cpp').read_text()
        start=source.index('static TyvorFlightData readTyvorHomeFlightData(')
        end=source.index('{',start)+1;depth=1
        while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
        code=r'''
#include "gui/128x64/tyvor_flight_data.h"
#include <cassert>
#include <cstring>
#define CROSSFIRE
constexpr int MODULE_TYPE_NONE=0,TELEM_TYPE_CUSTOM=0,MAX_TELEMETRY_SENSORS=10;
constexpr int UNIT_RAW=0,UNIT_VOLTS=1,UNIT_MILLIWATTS=2,UNIT_DBM=3,UNIT_TEXT=4,UNIT_PERCENT=5,UNIT_METERS=6;
constexpr int BATTERY_ID=0x08,GPS_ID=0x02,LINK_ID=0x14,LINK_TX_ID=0x1d,FLIGHT_MODE_ID=0x21,BARO_ALT_ID=0x09;
constexpr int TELEMETRY_SENSOR_TIMEOUT_START=125;
struct Sensor{int id=0,instance=0,unit=0,prec=0,type=0,subId=0;bool available=false;bool autoOffset=false,filter=false,onlyPositive=false;struct{int ratio=0,offset=0;}custom;bool isAvailable()const{return available;}};
struct{struct{int type=0;}moduleData[2];Sensor telemetrySensors[10];}g_model;
using tmr10ms_t=uint32_t;tmr10ms_t now=0;tmr10ms_t get_tmr10ms(){return now;}
struct Item{int32_t value=0;int timeout=-2;char text[16]={};uint32_t tyvorReceivedAt=0;};Item telemetryItems[10];
TyvorArmState tyvorHomeFcArm(){return TyvorArmState::Unknown;}
bool streaming=true;bool TELEMETRY_STREAMING(){return streaming;}
bool isModuleCrossfire(int i){return g_model.moduleData[i].type==1;}
'''+source[start:end]+r'''
void sensor(int i,int id,int instance,int unit,int value,int prec=0){g_model.telemetrySensors[i]={id,instance,unit,prec,0,0,true};telemetryItems[i]={value,125};}
int main(){
 g_model.moduleData[0].type=1;
 auto d=readTyvorHomeFlightData();assert(!d.batteryValid&&!d.powerValid&&!d.satellitesValid&&d.arm==TyvorArmState::Unknown);
 sensor(0,BATTERY_ID,0,UNIT_VOLTS,152,1);sensor(1,GPS_ID,5,UNIT_RAW,12);sensor(2,LINK_ID,6,UNIT_MILLIWATTS,250);
 auto before=g_model;Item items[10];memcpy(items,telemetryItems,sizeof(items));
 d=readTyvorHomeFlightData();assert(d.batteryValid&&d.batteryDecivolts==152&&d.satellitesValid&&d.satellites==12&&d.powerValid&&d.power==250&&!d.powerDbm&&d.arm==TyvorArmState::Unknown);
 assert(!memcmp(&before,&g_model,sizeof(before))&&!memcmp(items,telemetryItems,sizeof(items)));
 telemetryItems[1].timeout=93;d=readTyvorHomeFlightData();assert(!d.satellitesValid&&d.batteryValid);
 telemetryItems[1].timeout=94;assert(readTyvorHomeFlightData().satellitesValid);
 telemetryItems[0].timeout=-1;assert(!readTyvorHomeFlightData().batteryValid);
 telemetryItems[0].timeout=125;streaming=false;d=readTyvorHomeFlightData();assert(!d.batteryValid&&!d.powerValid&&!d.satellitesValid);streaming=true;
 sensor(3,BATTERY_ID,0,UNIT_VOLTS,168,1);assert(!readTyvorHomeFlightData().batteryValid);g_model.telemetrySensors[3].available=false;
 g_model.telemetrySensors[0].unit=UNIT_RAW;assert(!readTyvorHomeFlightData().batteryValid);g_model.telemetrySensors[0].unit=UNIT_VOLTS;
 g_model.telemetrySensors[0].type=1;assert(!readTyvorHomeFlightData().batteryValid);g_model.telemetrySensors[0].type=0;
 g_model.moduleData[1].type=1;assert(!readTyvorHomeFlightData().batteryValid);g_model.moduleData[1].type=2;assert(!readTyvorHomeFlightData().batteryValid);g_model.moduleData[1].type=0;
 g_model.telemetrySensors[2].available=false;sensor(4,LINK_TX_ID,1,UNIT_DBM,24);d=readTyvorHomeFlightData();assert(d.powerValid&&d.powerDbm&&d.power==24);
 g_model.telemetrySensors[2].available=true;d=readTyvorHomeFlightData();assert(d.powerValid&&!d.powerDbm&&d.power==250);
 telemetryItems[0].value=-1;telemetryItems[1].value=256;telemetryItems[2].value=1000001;g_model.telemetrySensors[4].available=false;
 d=readTyvorHomeFlightData();assert(!d.batteryValid&&!d.satellitesValid&&!d.powerValid&&d.arm==TyvorArmState::Unknown);
 uint16_t value;assert(tyvorFlightVoltage(1568,2,value)&&value==157);assert(!tyvorFlightVoltage(INT32_MAX,0,value));assert(!tyvorFlightVoltage(-1,1,value));
 char text[16];d={};tyvorFlightBatteryText(text,d);assert(!strcmp(text,"--"));tyvorFlightSatsText(text,d);assert(!strcmp(text,"--"));tyvorFlightPowerText(text,d);assert(!strcmp(text,"--"));
 d.batteryValid=d.satellitesValid=d.powerValid=true;d.batteryDecivolts=152;d.satellites=12;d.power=250;
 tyvorFlightBatteryText(text,d);assert(!strcmp(text,"15.2V"));tyvorFlightSatsText(text,d);assert(!strcmp(text,"12"));tyvorFlightPowerText(text,d);assert(!strcmp(text,"250mW"));
 d.power=2500;tyvorFlightPowerText(text,d);assert(!strcmp(text,"2.5W"));
 assert(!strcmp(tyvorArmLabel(TyvorArmState::Unknown),"UNKNOWN"));
 sensor(0,BATTERY_ID,0,UNIT_VOLTS,152,1);sensor(3,BATTERY_ID,3,UNIT_PERCENT,80);
 sensor(6,FLIGHT_MODE_ID,0,UNIT_TEXT,0);strcpy(telemetryItems[6].text,"HORIZON");
 d=readTyvorHomeFlightData();assert(d.modeValid&&!strcmp(d.mode,"HORIZON")&&d.batteryPercentValid&&tyvorDroneBatteryBars(d)==4&&d.arm==TyvorArmState::Unknown);
 telemetryItems[0].value=32;d=readTyvorHomeFlightData();assert(tyvorDroneBatteryBars(d)==4); // same reported %, not derived from voltage
 telemetryItems[3].value=0;assert(tyvorDroneBatteryBars(readTyvorHomeFlightData())==0);
 telemetryItems[3].value=1;assert(tyvorDroneBatteryBars(readTyvorHomeFlightData())==1);
 telemetryItems[3].value=34;assert(tyvorDroneBatteryBars(readTyvorHomeFlightData())==2);
 telemetryItems[3].value=100;assert(tyvorDroneBatteryBars(readTyvorHomeFlightData())==5);
 telemetryItems[3].value=101;assert(tyvorDroneBatteryBars(readTyvorHomeFlightData())==-1);
 telemetryItems[3].value=80;telemetryItems[0].timeout=-1;assert(tyvorDroneBatteryBars(readTyvorHomeFlightData())==-1);telemetryItems[0].timeout=125;
 telemetryItems[3].timeout=93;assert(tyvorDroneBatteryBars(readTyvorHomeFlightData())==-1);telemetryItems[3].timeout=125;
 telemetryItems[6].timeout=112;assert(!readTyvorHomeFlightData().modeValid);telemetryItems[6].timeout=113;assert(readTyvorHomeFlightData().modeValid);
 sensor(7,FLIGHT_MODE_ID,0,UNIT_TEXT,0);strcpy(telemetryItems[7].text,"ACRO");assert(!readTyvorHomeFlightData().modeValid);g_model.telemetrySensors[7].available=false;
 strcpy(telemetryItems[6].text,"ARMED");d=readTyvorHomeFlightData();assert(d.modeValid&&d.arm==TyvorArmState::Unknown);
 strcpy(telemetryItems[6].text,"BAD\nMODE");assert(!readTyvorHomeFlightData().modeValid);
 char mode[17];assert(!tyvorFlightModeText("   ",3,mode));assert(tyvorFlightModeText("  ANGLE  ",9,mode)&&!strcmp(mode,"ANGLE"));
 assert(tyvorFlightModeText("ABCDEFGHIJKLMNOP",16,mode)&&strlen(mode)==16);
 sensor(4,BATTERY_ID,3,UNIT_PERCENT,20);assert(!readTyvorHomeFlightData().batteryPercentValid);g_model.telemetrySensors[4].available=false;
 for(int percent=0;percent<=100;percent++){
  telemetryItems[3].value=percent;
  assert(tyvorDroneBatteryBars(readTyvorHomeFlightData())==(percent+19)/20);
 }
 strcpy(telemetryItems[6].text,"ANGLE");
 now=192;assert(readTyvorHomeFlightData().modeValid);now=193;assert(!readTyvorHomeFlightData().modeValid);
 now=496;assert(readTyvorHomeFlightData().batteryValid);now=497;assert(!readTyvorHomeFlightData().batteryValid);
 assert(tyvorFlightReceivedRecently(4,UINT32_MAX-5,10));assert(!tyvorFlightReceivedRecently(5,UINT32_MAX-5,10));
 now=0;
 sensor(8,LINK_ID,2,UNIT_PERCENT,50);sensor(9,LINK_ID,8,UNIT_PERCENT,100);
 d=readTyvorHomeFlightData();assert(d.linkQualityValid&&d.linkQuality==50&&tyvorHomeLinkBars(d)==3);
 telemetryItems[9].value=0;assert(readTyvorHomeFlightData().linkQuality==50);
 for(int q=0;q<=100;++q){telemetryItems[8].value=q;d=readTyvorHomeFlightData();assert(d.linkQualityValid&&tyvorHomeLinkBars(d)==(q*5+50)/100);}
 telemetryItems[8].value=101;assert(!readTyvorHomeFlightData().linkQualityValid);telemetryItems[8].value=-1;assert(!readTyvorHomeFlightData().linkQualityValid);telemetryItems[8].value=50;
 g_model.telemetrySensors[8].unit=UNIT_RAW;assert(!readTyvorHomeFlightData().linkQualityValid);g_model.telemetrySensors[8].unit=UNIT_PERCENT;
 g_model.telemetrySensors[8].prec=1;assert(!readTyvorHomeFlightData().linkQualityValid);g_model.telemetrySensors[8].prec=0;
 g_model.telemetrySensors[8].custom.offset=1;assert(!readTyvorHomeFlightData().linkQualityValid);g_model.telemetrySensors[8].custom.offset=0;
 now=100;assert(readTyvorHomeFlightData().linkQualityValid);now=101;assert(!readTyvorHomeFlightData().linkQualityValid);now=0;
 telemetryItems[8].timeout=117;assert(!readTyvorHomeFlightData().linkQualityValid);telemetryItems[8].timeout=125;
 g_model.telemetrySensors[9]=g_model.telemetrySensors[8];assert(!readTyvorHomeFlightData().linkQualityValid);g_model.telemetrySensors[9].available=false;
 streaming=false;d=readTyvorHomeFlightData();assert(!d.modeValid&&tyvorDroneBatteryBars(d)==-1&&!d.linkQualityValid);


}
'''
        with tempfile.TemporaryDirectory(prefix='tyvor-flight-data-') as temp:
            path=Path(temp);(path/'test.cpp').write_text(code)
            subprocess.run(['g++','-std=c++17','-fsanitize=undefined','-fno-sanitize-recover=all',
                            '-I',str(ROOT/'radio/src'),str(path/'test.cpp'),'-o',str(path/'test')],check=True)
            subprocess.run([str(path/'test')],check=True)
