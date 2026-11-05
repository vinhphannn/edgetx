"""Execute the real V2 loading UI and disk callbacks: settings load during a complete four-dot sequence."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[2] / 'src'


def function(source, signature):
    start=source.index(signature)
    pos=source.index('{',start)+1
    depth=1
    while depth:
        depth+=(source[pos]=='{')-(source[pos]=='}')
        pos+=1
    return source[start:pos]+'\n'


@unittest.skipUnless(shutil.which('g++'), 'requires host C++ compiler')
class PowerFeedbackTests(unittest.TestCase):
    def execute(self, source, variants=((),)):
        with tempfile.TemporaryDirectory() as tmp:
            cpp=Path(tmp)/'test.cpp';binary=Path(tmp)/'test';cpp.write_text(source)
            for flags in variants:
                build=subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror',
                                      *flags,str(cpp),'-o',str(binary)],capture_output=True,text=True)
                self.assertEqual(build.returncode,0,build.stderr)
                subprocess.run([str(binary)],check=True,timeout=5)

    def test_storage_progresses_during_dots_and_no_other_task_or_error_can_be_overwritten(self):
        source=(SRC/'edgetx.cpp').read_text()
        begin=source.index('static bool deveboxStartupDisplayActive;')
        end=source.index('\n#endif\n\nvoid edgeTxInit()',begin)
        header=SRC/'targets/taranis/devebox_v2/devebox_diagnostics.h'
        code='#define SAOLALINK_DEVEBOX_V2\n#include "'+str(header)+'"\n'
        code+=r'''
#include <cassert>
#include <cstring>
#include <string>
#include <vector>
DeveboxStartupTiming deveboxStartupTiming={};
const char* volatile deveboxStartupStatus;
using TaskHandle_t=unsigned;
static uint32_t now;
static unsigned currentTask=1,paints,rectangles;
static std::string drawn;
constexpr unsigned LCD_W=128,LCD_H=64,FH=8,SOLID=1;
TaskHandle_t xTaskGetCurrentTaskHandle() {return currentTask;}
uint32_t timersGetMsTick() {return now;}
void sleep_ms(uint32_t ms) {now+=ms;}
void lcdSetContrast(bool defaults) {assert(defaults);}
void lcdRefreshWait() {}
void lcdClear() {drawn.clear();rectangles=0;}
unsigned getTextWidth(const char* text) {return strlen(text)*6;}
void lcdDrawText(unsigned,unsigned,const char* text) {drawn=text;}
void lcdDrawFilledRect(unsigned x,unsigned y,unsigned w,unsigned h,unsigned style,unsigned flags) {
 assert(x==LCD_W/2-18+10*rectangles && y==LCD_H/2-3 && w==6 && h==6);
 assert(style==SOLID && flags==0);++rectangles;
}
void lcdRefresh() {assert(currentTask==1);++paints;}
static void (*progressCallback)();
void sdcard_spi_set_progress_callback(void (*callback)()) {progressCallback=callback;}
'''+source[begin:end]+r'''
int main() {
 now=0;deveboxStartupDisplay();
 assert(now==0 && paints==1 && drawn.empty()); // no pre-load wait
 assert(progressCallback==deveboxStartupDisplayProgress);
 unsigned reads=0;
 for(unsigned block=0;block<8;++block) {
  now+=50;++reads;progressCallback(); // model/radio data being read
  assert(drawn.empty() && paints==reads+1);
 }
 assert(reads==8 && now==400 && rectangles==2); // data ready before 1-second dots
 deveboxStartupDisplayFinish();
 assert(now==1000 && rectangles==4 && deveboxStartupTiming.displayMs==1000);
 drawn="main menu";
 assert(progressCallback==nullptr);
 auto done=paints;now+=5000;deveboxStartupDisplayProgress();
 assert(paints==done && drawn=="main menu"); // animation cannot overwrite main menu
 now=10000;deveboxStartupDisplay();done=paints;
 now+=50;currentTask=2;deveboxStartupDisplayProgress();assert(paints==done);
 currentTask=1;deveboxStartupDisplayProgress();assert(paints==done+1);
 done=paints;now+=10;deveboxStartupDisplayProgress();assert(paints==done); // rate limit
 deveboxStartupDisplayStop();drawn="NO SD CARD";
 auto errorTime=now;deveboxStartupDisplayFinish();assert(now==errorTime);
 now+=2000;deveboxStartupDisplayProgress();assert(drawn=="NO SD CARD");
 now=20000;deveboxStartupDisplay();now+=1400;deveboxStartupDisplayProgress();
 assert(rectangles==4); // slow SD keeps four dots instead of restarting the count
 auto readyTime=now;deveboxStartupDisplayFinish();
 assert(now==readyTime && deveboxStartupTiming.displayMs==1400);
 now=0xFFFFFF00U;deveboxStartupDisplay();now+=400;deveboxStartupDisplayProgress();
 assert(rectangles==2 && deveboxStartupTiming.progressFrames==2); // timer wrap
 deveboxStartupDisplayFinish();assert(deveboxStartupTiming.displayMs==1000 && rectangles==4);
}
'''
        self.execute(code)

    def test_disk_callbacks_run_after_completed_transactions_and_preserve_io_failures(self):
        disk=(SRC/'targets/common/arm/stm32/diskio_spi.cpp').read_text()
        code=r'''
#include <cassert>
#include <cstdint>
#include <vector>
using BYTE=uint8_t;using DWORD=uint32_t;using UINT=unsigned;using DSTATUS=int;using DRESULT=int;
using sd_rw_response_t=int;
constexpr int SDCARD_SPI_OK=0,STA_NOINIT=1,RES_OK=0,RES_ERROR=1,SD_RW_OK=0,SD_HC_BLOCK_SIZE=512;
struct sdcard_info_t {};
static int _sd_spi_hw;
static uint32_t _sdcard_sectors;
static bool fail, inFlight;
static std::vector<int> calls;
int sdcard_spi_init(int*,sdcard_info_t*) {calls.push_back(1);return fail?1:0;}
unsigned sdcard_spi_get_sector_count(sdcard_info_t*) {return 500;}
void sdcard_spi_read_blocks(DWORD,BYTE*,int,UINT,sd_rw_response_t* state) {
 inFlight=true;calls.push_back(1);*state=fail?1:0;inFlight=false;
}
void sdcard_spi_write_blocks(DWORD,const BYTE*,int,UINT,sd_rw_response_t* state) {
 inFlight=true;calls.push_back(1);*state=fail?1:0;inFlight=false;
}
void deveboxStartupDisplayProgress() {assert(!inFlight);calls.push_back(2);}
'''
        start=disk.index('#if defined(SAOLALINK_DEVEBOX_V2)',disk.index('static uint32_t _sdcard_sectors;'))
        end=disk.index('\n#endif',start)+len('\n#endif')
        code+=disk[start:end]+'\n'
        for signature in ('static DSTATUS sdcard_spi_initialize(BYTE lun)',
                          'static DRESULT sdcard_spi_read(BYTE lun, BYTE * buff, DWORD sector, UINT count)',
                          'static DRESULT sdcard_spi_write(BYTE lun, const BYTE* buff, DWORD sector, UINT count)'):
            code+=function(disk,signature).replace('BYTE lun','BYTE /*lun*/')
        code+=r'''
static bool registered;
static void checkCalls() {
#if defined(SAOLALINK_DEVEBOX_V2)
 assert(calls==(registered?std::vector<int>({1,2}):std::vector<int>({1})));
#else
 assert(calls==std::vector<int>({1}));
#endif
 calls.clear();
}
int main() {
 BYTE data[512]={};
 // The shared disk module must work in bootloader with no app UI linked.
 assert(sdcard_spi_read(0,data,0,1)==RES_OK);checkCalls();
#if defined(SAOLALINK_DEVEBOX_V2)
 sdcard_spi_set_progress_callback(deveboxStartupDisplayProgress);
#endif
 registered=true;
 for(bool error:{false,true}) {
  fail=error;
  assert(sdcard_spi_initialize(0)==(error?STA_NOINIT:0));checkCalls();
  assert(sdcard_spi_read(0,data,0,1)==(error?RES_ERROR:RES_OK));checkCalls();
  assert(sdcard_spi_write(0,data,0,1)==(error?RES_ERROR:RES_OK));checkCalls();
 }
#if defined(SAOLALINK_DEVEBOX_V2)
 sdcard_spi_set_progress_callback(nullptr);
#endif
 registered=false;fail=false;
 assert(sdcard_spi_read(0,data,0,1)==RES_OK);checkCalls();
}
'''
        self.execute(code,variants=((),('-DSAOLALINK_DEVEBOX_V2',),
                                    ('-DSAOLALINK_DEVEBOX_V2','-DBOOT')))

    def test_progress_is_stopped_before_model_ui_and_error_prompts(self):
        app=(SRC/'edgetx.cpp').read_text()
        startup=function(app,'void edgeTxInit()')
        self.assertLess(startup.index('deveboxStartupDisplay();'),startup.index('storageReadRadioSettings(false);'))
        self.assertLess(startup.index('storageReadAll();'),startup.index('deveboxStartupDisplayFinish();'))
        self.assertLess(startup.index('deveboxStartupDisplayFinish();'),startup.index('initSerialPorts();'))
        alert=function(app,'void alert(const char * title, const char * msg , uint8_t sound)')
        self.assertLess(alert.index('deveboxStartupDisplayStop();'),alert.index('RAISE_ALERT('))
        draw=(SRC/'gui/common/stdlcd/draw_functions.cpp').read_text()
        fatal=function(draw,'void drawFatalErrorScreen(const char * message)')
        self.assertLess(fatal.index('deveboxStartupDisplayStop();'),fatal.index('lcdClear();'))
