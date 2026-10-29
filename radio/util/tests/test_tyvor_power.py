"""Execute the firmware power renderer and nonblocking splash state on a host.

Pixel/font appearance is additionally checked in the real native SDL simulator;
this harness checks timing, cancellation, bounds and target isolation.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'radio/src'


@unittest.skipUnless(shutil.which('g++'), 'requires host g++')
class TyvorPowerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='tyvor-power-')
        cls.addClassCleanup(cls.tmp.cleanup)
        root = Path(cls.tmp.name)
        for name in ('hal/rgbleds.h', 'boards/generic_stm32/rgb_leds.h',
                     'inactivity_timer.h', 'os/sleep.h'):
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('')
        (root / 'sleep.lbm').write_text('42,47,0')
        for name in ('tyvor_owl', 'splash', 'tyvor_wordmark'):
            bitmap = root / f'bitmaps/128x64/{name}.lbm'
            bitmap.parent.mkdir(parents=True, exist_ok=True)
            bitmap.write_text('100,16,0,' if name == 'tyvor_wordmark' else '128,64,0,')
        (root / 'edgetx.h').write_text(r'''
#pragma once
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
using std::min; using std::max;
using tmr10ms_t=uint32_t;
using coord_t=int16_t;
#define LCD_W 128
#define LCD_H 64
#define FH 8
#define DBLSIZE 1
#define MIDSIZE 2
#define SMLSIZE 4
#define CENTERED 8
#define FORCE 16
#define SOLID 255
#define INVERS 32
struct Text {int x,y,flags;std::string value;};
struct Rect {int x,y,w,h;};
inline std::vector<Text> texts;
inline std::vector<Rect> rects;
inline unsigned refreshes=0,waits=0,splashes=0,sleeps=0,owlFrames=0;
inline unsigned bitmapCalls=0;
inline int bitmapFlags=0;
inline int bitmapX=0,bitmapY=0,bitmapW=0,bitmapH=0;
inline uint32_t ticks=0;
inline bool enabled=true;
inline uint32_t get_tmr10ms() {return ticks;}
inline bool SPLASH_NEEDED() {return enabled;}
#define SPLASH_TIMEOUT 5
inline void resetBacklightTimeout() {}
inline void getADC() {}
inline bool inactivityCheckInputs() {return false;}
inline bool getEvent() {return false;}
inline int pwrCheck() {return 0;}
constexpr int e_power_off=1;
inline void checkBacklight() {}
inline void sleep_ms(unsigned) {++sleeps;++ticks;}
inline void lcdClear() {texts.clear();rects.clear();}
inline void lcdRefresh() {++refreshes;}
inline void lcdRefreshWait() {++waits;}
#if !defined(REAL_SPLASH_TEST)
inline void drawSplash() {++splashes;}
inline void drawTyvorSplashFrame() {++owlFrames;lcdClear();}
#endif
inline int getTextWidth(const char* s) {return strlen(s)*6;}
inline void lcdDrawText(int x,int y,const char* s,int flags=0) {
 int width=strlen(s)*((flags&DBLSIZE)?10:(flags&MIDSIZE)?8:(flags&SMLSIZE)?5:6);
 int height=(flags&DBLSIZE)?16:(flags&MIDSIZE)?12:(flags&SMLSIZE)?6:8;
 int left=(flags&CENTERED)?x-width/2:x;
 assert(left>=0&&left+width<=128&&y>=0&&y+height<=64);
 texts.push_back({x,y,flags,s});
}
inline void lcdDrawFilledRect(int x,int y,int w,int h,int,int) {
 assert(x>=0&&x+w<=128&&y>=0&&y+h<=64);rects.push_back({x,y,w,h});
}
inline void lcdDraw1bitBitmap(int x,int y,const unsigned char* b,int,int flags=0) {
 assert(x>=0&&y>=0&&x+b[0]<=128&&y+b[1]<=64);
 ++bitmapCalls;bitmapFlags=flags;bitmapX=x;bitmapY=y;bitmapW=b[0];bitmapH=b[1];
}
#if !defined(REAL_SPLASH_TEST)
inline void drawTyvorBrand(coord_t y) {lcdDrawText(64,y,"TYVOR",DBLSIZE|CENTERED);}
#endif
template<class T> T limit(T lo,T v,T hi) {return std::clamp(v,lo,hi);}
''')
        code = f'''#include "{SRC}/gui/128x64/startup_shutdown.cpp"\n#include "{SRC}/gui/common/stdlcd/splash.cpp"\n'''
        code += r'''
int main(int argc,char**argv) {
 const std::string mode=argv[1];
#if defined(TYVOR_POWER_UI)
 if(mode=="boot") {
  ticks=100;startSplash();waitSplash();assert(sleeps==0&&splashes==0);
  for(unsigned i=0;i<120;++i) {
   ticks=100+i;assert(drawTyvorStartup(false));
   assert(texts.size()==1&&texts[0].value=="Starting...");
   assert(rects.size()==52+std::min(64U,i*64/110));
   assert(refreshes==0&&waits==0); // integrated into guiMain's single refresh
  }
  for(unsigned i=120;i<270;++i) {
   ticks=100+i;assert(drawTyvorStartup(false));
   assert(owlFrames==i-119&&texts.empty()&&rects.empty());
   assert(refreshes==0&&waits==0&&sleeps==0); // original owl uses GUI refresh too
  }
  ticks=370;assert(!drawTyvorStartup(false));
  ticks=400;assert(!drawTyvorStartup(false));assert(splashes==0&&owlFrames==150);
 } else if(mode=="progress") {
  // Execute all tick masks. Every added outer-ring pixel advances clockwise;
  // previous pixels and the power symbol remain white, including completion.
  bool before[64][128]={}; unsigned changes=0;
  for(unsigned t=0;t<=130;++t) {
   drawTyvorPowerFrame(t,120,false);
   bool pixels[64][128]={};
   for(const auto&r:rects)for(int y=r.y;y<r.y+r.h;y++)for(int x=r.x;x<r.x+r.w;x++)pixels[y][x]=true;
   bool changed=false;
   for(int y=0;y<64;y++)for(int x=0;x<128;x++) {
    assert(!before[y][x]||pixels[y][x]);changed|=before[y][x]!=pixels[y][x];
   }
   if(t>=110)assert(!changed || t==110);
   if(changed)++changes;
   memcpy(before,pixels,sizeof(before));
   // 25% at the right, then 50% at the bottom, 75% at the left.
   if(t==0)assert(!pixels[9][63]&&!pixels[25][79]);
   if(t==30)assert(pixels[9][63]&&pixels[25][79]&&!pixels[41][63]);
   if(t==60)assert(pixels[41][63]&&!pixels[25][47]);
   if(t==90)assert(pixels[25][47]);
   assert(pixels[15][63]&&pixels[26][64]); // fixed power stem
   assert(texts.size()==1&&texts[0].value=="Starting...");
  }
  assert(changes==65); // initial symbol plus exactly 64 cumulative ring steps
  // Zero and extreme callers still stay in bounds without multiplication overflow.
  drawTyvorPowerFrame(0,0,false);drawTyvorPowerFrame(UINT32_MAX,UINT32_MAX,false);
  ticks=100;startSplash();waitSplash();ticks=180;drawTyvorStartup(false);
  auto previous=rects.size();ticks=170;drawTyvorStartup(false);assert(rects.size()==previous);
  ticks=220;drawTyvorStartup(false);assert(owlFrames==1);
  ticks=215;drawTyvorStartup(false);assert(owlFrames==2); // no return to loading
 } else if(mode=="cancel") {
  for(unsigned stage:{0U,120U}) {
  for(unsigned reason=0;reason<4;++reason) {
   ticks=20;startSplash();waitSplash();
   ticks+=stage;assert(drawTyvorStartup(false));
   if(reason==0) cancelSplash();
   else if(reason==1) {enabled=false;waitSplash();}
   else if(reason==2) {assert(!drawTyvorStartup(true));}
   else ticks=290;
   assert(!drawTyvorStartup(false));enabled=true;
   ticks=160;assert(!drawTyvorStartup(false)); // cancellation cannot resume the owl
   ticks=260;assert(!drawTyvorStartup(false));
  }
  }
  // A NO_SPLASH caller never arms the overlay even if waitSplash is called.
  cancelSplash();waitSplash();assert(!drawTyvorStartup(false));
 } else if(mode=="wrap") {
  ticks=0xfffffff0;startSplash();waitSplash();
  ticks=0x10;assert(drawTyvorStartup(false));assert(rects.size()==70);
  ticks=0x68;assert(drawTyvorStartup(false));assert(owlFrames==1);
  ticks=0xfd;assert(drawTyvorStartup(false));assert(owlFrames==2);
  ticks=0xfe;assert(!drawTyvorStartup(false));
 } else if(mode=="shutdown") {
  for(unsigned total:{1U,2U,10U,50U,100U,200U,300U}) {
   resetTyvorShutdown();
   const unsigned window=min(total,100U);
   bool before[64][128]={};
   for(unsigned i=0;i<=total+5;++i) {
    drawShutdownAnimation(i,total,"Model still powered");
    unsigned progress=min(i,window)*64/window;
    assert(texts.size()==2&&texts[0].value=="Shutting down..."&&texts[1].value=="Model still powered");
    assert(rects.size()==52+64-progress);
    bool pixels[64][128]={};
    for(const auto&r:rects)for(int y=r.y;y<r.y+r.h;y++)for(int x=r.x;x<r.x+r.w;x++)pixels[y][x]=true;
    if(i)for(int y=0;y<64;y++)for(int x=0;x<128;x++)assert(!pixels[y][x]||before[y][x]);
    memcpy(before,pixels,sizeof(before));
   }
   drawSleepBitmap();assert(rects.size()==52&&texts[0].value=="Shutting down..."&&splashes==0);
   drawShutdownAnimation(0,100,nullptr);assert(rects.size()==52); // never restart after completion
   drawTyvorStartup(false); // normal HOME after a cancelled hold resets the ring
   drawShutdownAnimation(0,total,nullptr);assert(rects.size()==116);
   drawShutdownAnimation(window/2,total,nullptr);auto count=rects.size();
   drawShutdownAnimation(0,total,nullptr);assert(rects.size()==count); // backwards caller cannot refill
  }
  resetTyvorShutdown();drawShutdownAnimation(10,200,nullptr);assert(rects.size()==116); // first frame full
  auto count=refreshes;drawShutdownAnimation(0,0,nullptr);assert(count==refreshes);
  drawTyvorPowerFrame(UINT32_MAX,UINT32_MAX,true);assert(rects.size()==52);
  // The erased boundary moves counterclockwise: upper left, left, bottom, right.
  for(unsigned t:{0U,25U,50U,75U,100U}) {
   drawTyvorPowerFrame(t,100,true);bool pixels[64][128]={};
   for(const auto&r:rects)for(int y=r.y;y<r.y+r.h;y++)for(int x=r.x;x<r.x+r.w;x++)pixels[y][x]=true;
   if(t==0)assert(pixels[9][63]&&pixels[25][47]&&pixels[41][63]&&pixels[25][79]);
   if(t==25)assert(!pixels[25][47]&&pixels[41][63]&&pixels[25][79]);
   if(t==50)assert(!pixels[41][63]&&pixels[25][79]);
   if(t==75)assert(!pixels[25][79]&&pixels[9][63]);
   if(t==100)assert(!pixels[9][63]&&pixels[15][63]);
  }
 }

#else
 assert(mode=="generic");
 drawStartupAnimation(0,100);assert(rects.empty()&&texts.empty());
 drawStartupAnimation(80,100);assert(rects.size()==4&&texts.empty());
 drawShutdownAnimation(0,100,"hold");assert(rects.size()==4&&texts.size()==1&&texts[0].value=="hold");
 auto count=refreshes;drawShutdownAnimation(0,0,nullptr);assert(count==refreshes);
#endif
}
'''
        (root / 'check.cpp').write_text(code)
        cls.binaries = {}
        for name, defines in {'devebox': ['RADIO_SAOLALINKV1', 'SAOLALINK_DEVEBOX'], 'generic': []}.items():
            binary = root / name
            subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Wno-unused-parameter',
                            '-I', str(root), '-I', str(SRC), *['-D'+d for d in defines],
                            str(root/'check.cpp'), '-o', str(binary)], check=True, capture_output=True, text=True)
            cls.binaries[name] = binary

        # Exercise the actual owl renderer and the legacy refresh API as well.
        real = root / 'real_splash.cpp'
        real.write_text(f'#include "{SRC}/gui/128x64/splash.cpp"\n' + r'''
int main() {
#if defined(TYVOR_POWER_UI)
 drawTyvorSplashFrame();
 assert(refreshes==0&&waits==0&&bitmapFlags==INVERS);
#if defined(BOOT)
 assert(bitmapCalls==1&&texts.size()==1&&texts[0].value=="TYVOR"&&texts[0].y==43);
#else
 assert(bitmapCalls==2&&texts.empty());
 assert(bitmapX==14&&bitmapY==43&&bitmapW==100&&bitmapH==16);
#endif
#endif
 auto before=refreshes;drawSplash();assert(refreshes==before+1&&waits==0);
}
''')
        for name, defines in {'owl': ['RADIO_SAOLALINKV1', 'SAOLALINK_DEVEBOX'], 'bootloader': ['RADIO_SAOLALINKV1', 'SAOLALINK_DEVEBOX', 'BOOT'], 'legacy': []}.items():
            binary = root / name
            subprocess.run(['g++', '-std=c++17', '-DREAL_SPLASH_TEST', '-I', str(root),
                            '-I', str(SRC), *['-D'+d for d in defines],
                            str(real), '-o', str(binary)], check=True, capture_output=True, text=True)
            cls.binaries[name] = binary

    def run_mode(self, mode):
        subprocess.run([str(self.binaries['devebox']), mode], check=True, capture_output=True, text=True)

    def test_boot_loading_then_original_owl_then_home_without_waits(self):
        self.run_mode('boot')

    def test_clockwise_progress_is_cumulative_single_shot_and_clamped(self):
        self.run_mode('progress')

    def test_input_warning_calibration_and_disabled_splash_can_cancel(self):
        self.run_mode('cancel')

    def test_tick_wrap_does_not_extend_boot(self):
        self.run_mode('wrap')

    def test_shutdown_counterclockwise_once_clamp_cancel_and_unchanged_deadline(self):
        self.run_mode('shutdown')

    def test_early_preview_precedes_model_loading_without_reordering_power(self):
        s=(SRC/'edgetx.cpp').read_text()
        a=s.index('void edgeTxInit()');b=s.index('void simuMain()',a)
        init=s[a:b]
        hook=init.index('drawStartupAnimation(0, 120);')
        self.assertLess(init.index('storageReadRadioSettings(false);'),hook)
        self.assertLess(init.index('lcdSetContrast();'),hook)
        self.assertLess(init.index('BACKLIGHT_ENABLE();'),hook)
        self.assertLess(hook,init.index('runStartupAnimation();'))
        self.assertLess(hook,init.index('storageReadAll();'))
        self.assertIn('!UNEXPECTED_SHUTDOWN() && SPLASH_NEEDED()',init[:hook])
        self.assertIn('!(startOptions & OPENTX_START_NO_SPLASH)',init[:hook])

    def test_other_radios_retain_their_original_power_ui(self):
        subprocess.run([str(self.binaries['generic']), 'generic'], check=True)

    def test_original_owl_frame_does_not_refresh_and_legacy_api_still_does(self):
        for name in ('owl', 'bootloader', 'legacy'):
            subprocess.run([str(self.binaries[name])], check=True)


if __name__ == '__main__':
    unittest.main()
