"""Exercise the firmware HOME timer formatter at its display boundaries."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(shutil.which('g++'), 'requires host g++')
class TyvorHomeTests(unittest.TestCase):
    def test_battery_icon_outline_unknown_and_reported_levels(self):
        source=(ROOT/'radio/src/gui/128x64/view_main.cpp').read_text()
        a=source.index('static void drawTyvorBatteryIcon(');b=source.index('{',a)+1;depth=1
        while depth:depth+=(source[b]=='{')-(source[b]=='}');b+=1
        code=r'''
#include <cstdint>
#include <cassert>
#include <cstring>
using coord_t=int16_t;
constexpr int FORCE=1,SOLID=255;
bool pixels[64][128];
void lcdDrawPoint(int x,int y,int){assert(x>=0&&x<128&&y>=0&&y<64);pixels[y][x]=true;}
void lcdDrawSolidHorizontalLine(int x,int y,int w,int f){for(int i=0;i<w;i++)lcdDrawPoint(x+i,y,f);}
void lcdDrawSolidVerticalLine(int x,int y,int h,int f){for(int i=0;i<h;i++)lcdDrawPoint(x,y+i,f);}
void lcdDrawSolidFilledRect(int x,int y,int w,int h,int f){for(int i=0;i<h;i++)lcdDrawSolidHorizontalLine(x,y+i,w,f);}
void lcdDrawRect(int x,int y,int w,int h,int,int f){lcdDrawSolidHorizontalLine(x,y,w,f);lcdDrawSolidHorizontalLine(x,y+h-1,w,f);lcdDrawSolidVerticalLine(x,y,h,f);lcdDrawSolidVerticalLine(x+w-1,y,h,f);}
'''+source[a:b]+r'''
int main(){
 bool unknown[64][128];
 for(int level=-1;level<=5;++level){
  memset(pixels,0,sizeof(pixels));drawTyvorBatteryIcon(10,10,level);
  for(int x=10;x<35;x++)assert(pixels[10][x]&&pixels[15][x]);
  for(int y=10;y<16;y++)assert(pixels[y][10]&&pixels[y][34]);
  for(int y=12;y<14;y++)assert(pixels[y][35]);
  int count=0;for(int y=0;y<64;y++)for(int x=0;x<128;x++)if(pixels[y][x]){assert(x>=10&&x<=35&&y>=10&&y<=15);++count;}
  assert(count==60+(level<0?8:6*level));
  if(level<0)memcpy(unknown,pixels,sizeof(pixels));
  else assert(memcmp(unknown,pixels,sizeof(pixels))!=0);
 }
}
'''
        with tempfile.TemporaryDirectory(prefix='tyvor-battery-icon-') as temp:
            path=Path(temp);(path/'test.cpp').write_text(code)
            subprocess.run(['g++','-std=c++17','-fsanitize=undefined','-fno-sanitize-recover=all',
                            str(path/'test.cpp'),'-o',str(path/'test')],check=True)
            subprocess.run([str(path/'test')],check=True)

    def test_flight_renderer_labels_and_bounds(self):
        def function(source, signature):
            start=source.index(signature);end=source.index('{',start)+1;depth=1
            while depth:
                depth+=(source[end]=='{')-(source[end]=='}');end+=1
            return source[start:end]+'\n'
        source=(ROOT/'radio/src/gui/128x64/view_main.cpp').read_text()
        code=r'''
#include "gui/128x64/tyvor_home.h"
#include "gui/128x64/tyvor_flight_data.h"
#include "gui/128x64/tyvor_timer.h"
#include <cassert>
#include <cstring>
#include <string>
#include <vector>
#include <initializer_list>
using coord_t=int16_t;using LcdFlags=uint32_t;
constexpr int ERASE=0;
#define BLINK_ON_PHASE 1
constexpr int FORCE=1,SOLID=255,SMLSIZE=0x100,MIDSIZE=0x200,DBLSIZE=0x300,TINSIZE=0x400;
constexpr int RIGHT=0x10000,CENTERED=0x20000,BOLD=0x40000,BLINK=0x80000,INVERS=0x100000;
struct Timer {int mode=1,start=0;bool showElapsed=false;};
struct {struct {char name[10];}header;Timer timers[1];} g_model;
struct {int currModel=0;int8_t vBatMin=-30,vBatMax=-40;}g_eeGeneral;
struct {int32_t val=0;}timersStates[1];
bool flightHasTime=true;uint32_t flightSeconds=0;
bool tyvorFlightTimerHasTime(){return flightHasTime;}
uint32_t tyvorFlightTimerSeconds(){return flightSeconds;}
const char* tyvorFlightTimerTag(){return "SW";}
TyvorFlightData fixture;
TyvorFlightData readTyvorHomeFlightData(){return fixture;}
struct Text{int x,y,w,h;std::string text;};std::vector<Text>texts;
int lcdLastLeftPos=0;unsigned g_vbat100mV=70;unsigned timerPoints=0;
int getTextWidth(const char* s,int len=0,int flags=0){int n=len?len:strlen(s);int f=flags&0xf00;return n*(f==DBLSIZE?10:f==MIDSIZE?8:f==SMLSIZE?5:f==TINSIZE?4:6);}
void lcdDrawText(int x,int y,const char*s,int flags=0){int w=getTextWidth(s,0,flags),f=flags&0xf00,h=f==DBLSIZE?14:f==MIDSIZE?10:f==SMLSIZE?6:f==TINSIZE?5:7;int left=(flags&CENTERED)?x-w/2:(flags&RIGHT)?x-w:x;assert(left>=0&&left+w<=128&&y>=0&&y+h<=64);texts.push_back({left,y,w,h,s});lcdLastLeftPos=left;}
void drawModelName(int x,int y,char* name,int,int f){char s[11]={};memcpy(s,name,10);lcdDrawText(x,y,*s?s:"MODEL01",f);}
void putsVBat(int x,int y,int flags){lcdDrawText(x,y,"7.0V",flags);}
bool IS_TXBATT_WARNING(){return false;}bool isAsteriskDisplayed(){return false;}
void lcdDrawChar(int x,int y,char c,int f){char s[]={c,0};lcdDrawText(x,y,s,f);}
void lcdDrawSolidHorizontalLine(int x,int y,int w,int){assert(x>=0&&x+w<=128&&y>=0&&y<64);}
void lcdDrawSolidVerticalLine(int x,int y,int h,int){assert(x>=0&&x<128&&y>=0&&y+h<=64);}
void lcdDrawPoint(int x,int y,int){assert(x>=5&&x<=70&&y>=23&&y<35);++timerPoints;}
void lcdDrawSolidFilledRect(int x,int y,int w,int h,int){assert(x>=0&&x+w<=128&&y>=0&&y+h<=64);}
void lcdDrawSizedText(int x,int y,const char*s,int n,int f){std::string t(s,n);lcdDrawText(x,y,t.c_str(),f);}
unsigned zlen(const char*s,unsigned n){unsigned i=0;while(i<n&&s[i])++i;return i;}
void lcdDrawRect(int x,int y,int w,int h,int,int){assert(x>=0&&x+w<=128&&y>=0&&y+h<=64);}
'''
        code+=function(source,'static void drawTyvorBatteryIcon(')
        code+=function(source,'static void drawTyvorHomeMetric(')
        code+=function(source,'static void drawTyvorHomeTimer(')
        code+=function(source,'static void drawTyvorLinkQuality(')
        code+=function(source,'static void drawTyvorHome()')
        code+=r'''
bool has(const char*s){for(const auto&t:texts)if(t.text==s)return true;return false;}
int main(){
 memcpy(g_model.header.name,"WWWWWWWWWW",10);
 for(int32_t v: {0,272,-65,3661,4000000,INT32_MIN,INT32_MAX}){
  for(auto arm:{TyvorArmState::Unknown,TyvorArmState::Armed,TyvorArmState::Disarmed}){
   texts.clear();fixture.arm=arm;flightSeconds=v<0?uint32_t(0u-uint32_t(v)):uint32_t(v);timersStates[0].val=v;drawTyvorHome();
   assert(has("SATS")&&has("ALT")&&!has("GPS")&&!has("TX")&&has("MODE")&&has("TIME")&&has(tyvorArmLabel(arm))&&!has("CRUISE")&&!has("TYVOR")&&!has("T1"));
   for(size_t a=0;a<texts.size();++a)for(size_t b=a+1;b<texts.size();++b){const auto&u=texts[a];const auto&t=texts[b];assert(u.x+u.w<=t.x||t.x+t.w<=u.x||u.y+u.h<=t.y||t.y+t.h<=u.y);}
  }
 }
 fixture.batteryValid=fixture.satellitesValid=fixture.powerValid=true;
 fixture.batteryDecivolts=9999;fixture.satellites=255;fixture.power=1000000;fixture.altitudeValid=true;fixture.altitudeMeters=32766;
 texts.clear();drawTyvorHome();assert(has("999.9V")&&has("255")&&has("32766m")&&!has("1000W"));
 fixture.modeValid=true;strcpy(fixture.mode,"ABCDEFGHIJKLMNOP");texts.clear();drawTyvorHome();assert(has("ABCDEFGHIJKLMNOP"));
 fixture.modeValid=false;g_model.timers[0].mode=0;flightHasTime=false;texts.clear();drawTyvorHome();assert(!has("SW")&&!has("AUTO")&&!has("OFF")&&has("?")&&has("TIME")&&timerPoints);
}
'''
        with tempfile.TemporaryDirectory(prefix='tyvor-flight-render-') as temp:
            path=Path(temp);(path/'test.cpp').write_text(code)
            subprocess.run(['g++','-std=c++17','-fsanitize=undefined','-fno-sanitize-recover=all',
                            '-I',str(ROOT/'radio/src'),str(path/'test.cpp'),'-o',str(path/'test')],check=True)
            subprocess.run([str(path/'test')],check=True)

    def test_radio_battery_uses_only_valid_configured_range(self):
        code=r'''#include "gui/128x64/tyvor_home.h"
#include <cassert>
int main(){
 for(int v=0;v<256;v++)assert(tyvorRadioBatteryBars(v,0,0)==-1);
 assert(tyvorRadioBatteryBars(0,-30,-40)==-1);
 assert(tyvorRadioBatteryBars(70,-61,-40)==-1);
 assert(tyvorRadioBatteryBars(70,-30,41)==-1);
 assert(tyvorRadioBatteryBars(70,0,-40)==-1); // reversed range
 assert(tyvorRadioBatteryBars(70,-30,-60)==-1); // equal endpoints
 assert(tyvorRadioBatteryBars(60,-30,-40)==0);
 assert(tyvorRadioBatteryBars(33,-30,-40)==0);
 assert(tyvorRadioBatteryBars(70,-30,-40)==3);
 assert(tyvorRadioBatteryBars(80,-30,-40)==5);
 int last=0;for(int v=1;v<256;v++){
  int n=tyvorRadioBatteryBars(v,-30,-40);assert(n>=last&&n<=5);last=n;
 }
 // A different configured range changes the level; no fixed 7 V pattern.
 assert(tyvorRadioBatteryBars(70,-20,-36)==0);
 assert(tyvorRadioBatteryBars(70,-40,-50)==5);
}
'''
        with tempfile.TemporaryDirectory(prefix='tyvor-radio-range-') as temp:
            path=Path(temp);(path/'test.cpp').write_text(code)
            subprocess.run(['g++','-std=c++17','-fsanitize=undefined','-fno-sanitize-recover=all',
                            '-I',str(ROOT/'radio/src'),str(path/'test.cpp'),'-o',str(path/'test')],check=True)
            subprocess.run([str(path/'test')],check=True)

    def test_control_rail_limits(self):
        with tempfile.TemporaryDirectory(prefix='tyvor-rails-') as temp:
            path = Path(temp)
            (path/'test.cpp').write_text(r'''
#include "gui/128x64/tyvor_home.h"
#include <cassert>
int main() {
  assert(tyvorHomePosition(-1024,36,14)==36);
  assert(tyvorHomePosition(0,36,14)==43);
  assert(tyvorHomePosition(1024,36,14)==50);
  for (int value=-20000; value<=20000; ++value) {
    auto pot=tyvorHomePosition(value,36,14);
    auto stickX=tyvorHomePosition(value,71,15);
    auto stickY=tyvorHomePosition(value,35,13);
    auto trim=tyvorHomePosition(value,8,47,125);
    assert(pot>=36&&pot<=50);
    assert(stickX>=71&&stickX+3<=89);
    assert(stickY>=35&&stickY+3<=51);
    assert(trim>=8&&trim<=55);
  }
  assert(tyvorHomePosition(INT32_MIN,24,26,125)==24);
  assert(tyvorHomePosition(INT32_MAX,24,26,125)==50);
}
''')
            subprocess.run(['g++','-std=c++17','-fsanitize=undefined',
                            '-fno-sanitize-recover=all','-I',str(ROOT/'radio/src'),
                            str(path/'test.cpp'),'-o',str(path/'test')],check=True)
            subprocess.run([str(path/'test')],check=True)

    def test_phase2_widths_with_real_firmware_fonts(self):
        def function(source, signature):
            start=source.index(signature); end=source.index('{',start)+1; depth=1
            while depth:
                depth+=(source[end]=='{')-(source[end]=='}'); end+=1
            return source[start:end]+'\n'

        src=ROOT/'radio/src'
        with tempfile.TemporaryDirectory(prefix='tyvor-font-bounds-') as temp:
            path=Path(temp)
            names={'font_3x5':'font_03x05','font_4x6':'font_04x06',
                   'font_5x7':'font_05x07','font_5x7_B':'font_05x07_B_compressed',
                   'font_8x10':'font_08x10','font_10x14':'font_10x14_compressed',
                   'font_22x38_num':'font_22x38_num'}
            code='#include <cstdint>\n#include <cassert>\n#include <cstring>\n'
            code+='using LcdFlags=uint32_t;\nstruct PatternData {const uint8_t* data;uint8_t width,height;};\n'
            flags={'BOLD','FONTSIZE_MASK','FONTSIZE(x)','DBLSIZE','MIDSIZE','SMLSIZE','TINSIZE'}
            for line in (src/'gui/common/stdlcd/lcd_common.h').read_text().splitlines():
                words=line.split()
                if len(words)>1 and words[0]=='#define' and words[1] in flags:code+=line+'\n'
            code+=f'#include "{src}/gui/common/stdlcd/fonts.h"\n'
            for variable,name in names.items():
                encoded=path/(name+'.lbm')
                subprocess.run([sys.executable,'-B',str(ROOT/'tools/encode-font.py'),
                                str(src/'fonts/std'/(name+'.png')),str(encoded)],check=True)
                code+=f'const uint8_t {variable}[]={{'+encoded.read_text()+'};\n'
            code+='inline unsigned char map_utf8_char(const char*& s,uint8_t&) {return static_cast<unsigned char>(*s);}\n'
            common=(src/'gui/common/stdlcd/lcd_common.cpp').read_text()
            for signature in ['LcdFlags getCharPattern(', 'static uint8_t getPatternWidth(',
                              'uint8_t getCharWidth(', 'uint8_t getTextWidth(']:
                code+=function(common,signature)
            code+='#include "gui/128x64/tyvor_timer.h"\n'
            code+='LcdFlags choose(const char* text) {return getTextWidth(text,0,MIDSIZE)<=65?MIDSIZE:0;}\n'
            code+=r'''
#include "gui/128x64/tyvor_home.h"
int main() {
  assert(getTextWidth("WWWWWWWWWW",0,BOLD)<=70);
  assert(getTextWidth("DISARMED",0,SMLSIZE)<=40);
  assert(getTextWidth("WWW^",0,SMLSIZE)<=25);
  const char *mode="WWWWWWWWWWWWWWWW";
  auto modeFont=getTextWidth(mode,0,SMLSIZE)<=94?SMLSIZE:TINSIZE;
  assert(getTextWidth(mode,0,modeFont)<=94);
  for (int32_t value=-8388608; value<=8388607; value+=997) {
    char text[16];tyvorHomeTimerText(text,value);
    assert(tyvorTimerWidth(text)<=65 || getTextWidth(text,0,choose(text))<=65);
  }
  for (int32_t value: {int32_t(0),int32_t(272),int32_t(-65),INT32_MAX,INT32_MIN}) {
    char text[16];tyvorHomeTimerText(text,value);
    assert(tyvorTimerWidth(text)<=65 || getTextWidth(text,0,choose(text))<=65);
    if(value==272) {assert(tyvorTimerWidth(text)<getTextWidth(text,0,DBLSIZE));assert(tyvorTimerWidths[0]==7);}
  }
}
'''
            code='#include <initializer_list>\n'+code
            (path/'test.cpp').write_text(code)
            subprocess.run(['g++','-std=c++17','-fsanitize=undefined',
                            '-fno-sanitize-recover=all','-I',str(src),
                            str(path/'test.cpp'),'-o',str(path/'test')],check=True)
            subprocess.run([str(path/'test')],check=True)

    def test_timer_format_and_signed_extremes(self):
        with tempfile.TemporaryDirectory(prefix='tyvor-home-') as temp:
            path = Path(temp)
            (path / 'test.cpp').write_text(r'''
#include "gui/128x64/tyvor_home.h"
#include <cassert>
#include <cstring>
#include <limits>
int main() {
  struct Case {int32_t seconds; const char *text;};
  const Case cases[] = {
    {0,"00:00"}, {9,"00:09"}, {65,"01:05"}, {3599,"59:59"},
    {-1,"-00:01"}, {-65,"-01:05"}, {-3599,"-59:59"},
    {3600,"01h00"}, {3661,"01h01"}, {-3661,"-01h01"},
    {359999,"99h59"}, {360000,"100h"}, {-360000,"-100h"},
    {4000000,"1111h"}, {INT32_MAX,"596523h"}, {INT32_MIN,"-596523h"}
  };
  for (const auto &c: cases) {
    char text[16]; tyvorHomeTimerText(text,c.seconds);
    assert(!strcmp(text,c.text));
    // At most eight double-size glyphs: fits within the 120-pixel content area.
    assert(strlen(text)<=8);
  }
  // Sweep both signs throughout the valid EdgeTX timer range (23-bit signed).
  for (int32_t value=-8388608; value<=8388607; value+=997) {
    char text[16]; tyvorHomeTimerText(text,value);
    assert(strlen(text)<=8 && strchr(text,'\n')==nullptr);
  }
}
''')
            subprocess.run(['g++', '-std=c++17', '-fsanitize=undefined',
                            '-fno-sanitize-recover=all', '-I', str(ROOT/'radio/src'),
                            str(path/'test.cpp'), '-o', str(path/'test')], check=True)
            subprocess.run([str(path/'test')], check=True)


if __name__ == '__main__':
    unittest.main()
