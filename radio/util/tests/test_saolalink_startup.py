"""Regression tests for diagnostics during a blocking first-run/SD prompt."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[2] / 'src'


@unittest.skipUnless(shutil.which('g++'), 'requires host C++ compiler')
class StartupDiagnosticsTests(unittest.TestCase):
    def execute(self, source):
        with tempfile.TemporaryDirectory() as tmp:
            cpp = Path(tmp) / 'test.cpp'
            binary = Path(tmp) / 'test'
            cpp.write_text(source)
            result = subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                                     str(cpp), '-o', str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(binary)], check=True)

    def test_usb_is_usable_before_storage_prompt_and_saved_modes_are_restored(self):
        code = (SRC / 'tasks.cpp').read_text().split('static void menusTask()', 1)[1].split('  mixerTaskInit();', 1)[0]
        self.execute(r'''
#include <cassert>
#include <vector>
#define SAOLALINK_DEVEBOX 1
#define SAOLALINK_DEVEBOX_V2 1
#define USB_SERIAL 1
#define CLI 1
constexpr int SP_VCP=2, UART_MODE_CLI=7, USB_SERIAL_MODE=3, USB_UNSELECTED_MODE=0;
struct Settings {int USBMode;};
Settings g_eeGeneral;
const char* volatile deveboxStartupStatus;
static std::vector<int> events;
static bool block, connected;
static int savedUsb, savedSerial, loadedSerial;
struct WaitingForStorageKey {};
void serialInit(int port,int mode) { assert(port==SP_VCP && mode==UART_MODE_CLI); events.push_back(1); }
void setSelectedUsbMode(int mode) { events.push_back(mode==USB_SERIAL_MODE ? 2 : 6); }
void usbStart() { connected=true; events.push_back(3); }
void usbStop() { connected=false; events.push_back(4); }
void serialStop(int port) { assert(port==SP_VCP); events.push_back(5); }
int serialGetMode(int port) { assert(port==SP_VCP); return loadedSerial; }
void edgeTxInit() {
 assert(connected); // CDC must already be available if startup waits here
 if (block) throw WaitingForStorageKey{};
 g_eeGeneral.USBMode=savedUsb; loadedSerial=savedSerial;
}
static void menusTask()''' + code + r'''
}
int main() {
 block=true;
 try { menusTask(); assert(false); } catch(const WaitingForStorageKey&) {}
 assert(connected && events==std::vector<int>({1,2,3}));
 block=false;
 for (auto mode : {USB_SERIAL_MODE,USB_UNSELECTED_MODE,1}) {
  for (int serial : {UART_MODE_CLI,0}) {
   events.clear(); savedUsb=mode; savedSerial=serial;
   menusTask();
   bool preserve=(mode==USB_SERIAL_MODE && serial==UART_MODE_CLI);
   assert(connected==preserve);
   assert(events==(preserve ? std::vector<int>({1,2,3}) : std::vector<int>({1,2,3,4,5,6})));
   assert(g_eeGeneral.USBMode==mode); // starting diagnostics never rewrites settings
  }
 }
}
''')

    def test_startup_heartbeat_transitions_to_main_task_heartbeat(self):
        source = (SRC / 'main.cpp').read_text()
        start = source.index('void per5ms()')
        end = source.index('\n}\n', start) + 3
        hook = source[start:end]
        main_prefix = source.split('void perMain()', 1)[1].split('  DEBUG_TIMER_START', 1)[0]
        self.execute(r'''
#include <cassert>
#include <stdint.h>
#define SAOLALINK_DEVEBOX 1
#define SAOLALINK_DEVEBOX_V2 1
struct GPIO {uint32_t MODER, ODR;}; static GPIO gpio;
struct RCCType {uint32_t AHB1ENR;}; static RCCType rcc;
#define GPIOA (&gpio)
#define RCC (&rcc)
constexpr uint32_t RCC_AHB1ENR_GPIOAEN=1;
const char* volatile deveboxStartupStatus="hardware initialization";
using tmr10ms_t=uint32_t;
static uint32_t now;
uint32_t get_tmr10ms() { return now; }
static volatile bool deveboxMainRunning;
''' + hook + '\nvoid perMain()' + main_prefix + r'''
}
int main() {
 gpio.MODER=0xAAAAAAAA; gpio.ODR=0x55555555;
 auto original=gpio.ODR;
 for(int i=0;i<19;++i) per5ms();
 assert(gpio.ODR==original);
 per5ms();
 assert(gpio.ODR==(original^2));
 assert(gpio.MODER==((0xAAAAAAAA & ~(3U<<2)) | (1U<<2)));
 assert(rcc.AHB1ENR & RCC_AHB1ENR_GPIOAEN);
 now=0; perMain(); assert(deveboxMainRunning);
 auto startup= gpio.ODR;
 for(int i=0;i<200;++i) per5ms();
 assert(gpio.ODR==startup); // IRQ stops driving the startup indication
 now=50; perMain(); assert(gpio.ODR==(startup^2));
}
''')
