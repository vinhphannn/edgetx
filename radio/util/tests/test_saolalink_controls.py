"""Check generated switch hardware and run the actual CLI control monitors."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[2] / 'src'
RADIO = SRC.parent
TARGET = SRC / 'targets/taranis/saolalink_v1'


@unittest.skipUnless(shutil.which('g++'), 'requires host g++')
class DeveboxControlTests(unittest.TestCase):
    def compile_run(self, source):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cpp = root / 'controls.cpp'
            cpp.write_text(source)
            result = subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                                     str(cpp), '-o', str(root / 'controls')],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(root / 'controls')], check=True)

    @unittest.skipUnless(shutil.which('cmake'), 'requires cmake')
    def test_generated_switch_initialization_and_actual_position_driver(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'CMakeLists.txt').write_text(
                'cmake_minimum_required(VERSION 3.21)\nproject(controls NONE)\n'
                f'set(RADIO_SRC_DIR "{SRC}")\n'
                f'include("{TARGET / "adc_devebox.cmake"}")\n')
            subprocess.run(['cmake', '-S', str(root), '-B', str(root / 'build')],
                           check=True, capture_output=True, text=True)
            generated = subprocess.run([
                sys.executable, str(RADIO / 'util/hw_defs/generate_hw_def.py'), '-t',
                str(RADIO / 'util/hw_defs/stm32_switches.jinja'), '-T', 'saolalinkv1',
                str(root / 'build/saolalink-devebox-adc.json')],
                check=True, capture_output=True, text=True).stdout
        driver = (SRC / 'targets/common/arm/stm32/stm32_switch_driver.cpp').read_text()
        driver = 'SwitchHwPos stm32_switch_get_position(' + driver.split(
            'SwitchHwPos stm32_switch_get_position(', 1)[1]
        self.compile_run(r'''
#include <cassert>
#include <cstdint>
#include <cstring>
struct GPIO {uint32_t IDR=0xFFFF, initialized=0;};
static GPIO a,c,d,e;
#define GPIOA (&a)
#define GPIOC (&c)
#define GPIOD (&d)
#define GPIOE (&e)
#define LL_GPIO_MODE_INPUT 1
#define LL_GPIO_PULL_UP 2
struct LL_GPIO_InitTypeDef {unsigned Mode,Pull,Pin;};
void LL_GPIO_StructInit(LL_GPIO_InitTypeDef* p) {*p={};}
void stm32_gpio_enable_clock(GPIO*) {}
void LL_GPIO_Init(GPIO* gpio, LL_GPIO_InitTypeDef* p) {
  assert(p->Mode==LL_GPIO_MODE_INPUT && p->Pull==LL_GPIO_PULL_UP);
  gpio->initialized|=p->Pin;
}
int LL_GPIO_IsInputPinSet(GPIO* gpio, unsigned pin) {return (gpio->IDR & pin)!=0;}
enum SwitchHwType {SWITCH_HW_2POS,SWITCH_HW_3POS,SWITCH_HW_ADC};
enum SwitchHwPos {SWITCH_HW_UP,SWITCH_HW_MID,SWITCH_HW_DOWN};
enum SwitchConfig {SWITCH_2POS,SWITCH_3POS};
struct stm32_switch_t {
 const char* name; GPIO* GPIOx_high; unsigned Pin_high; GPIO* GPIOx_low;
 unsigned Pin_low; SwitchHwType type; bool inverted; SwitchConfig defaultType;
};
struct switch_display_pos_t {unsigned col,row;};
#define ADC_MAX_VALUE 4095
uint16_t getAnalogValue(unsigned) {return 0;}
''' + ''.join(f'#define LL_GPIO_PIN_{n} (1U << {n})\n' for n in range(16))
            + generated + '\n' + driver + r'''
int main() {
 _init_switches();
 assert(n_switches==4 && a.initialized==(1U<<5) && c.initialized==(1U<<13));
 assert(d.initialized==(1U<<11) && e.initialized==((1U<<15)|(1U<<8)));
 assert(!strcmp(_switch_defs[2].name,"SC"));
 assert(_switch_defs[2].type==SWITCH_HW_2POS && _switch_defs[2].defaultType==SWITCH_2POS);
 assert(_switch_defs[2].GPIOx_low==nullptr);
 assert(stm32_switch_get_position(&_switch_defs[0])==SWITCH_HW_UP);
 c.IDR&=~(1U<<13); assert(stm32_switch_get_position(&_switch_defs[0])==SWITCH_HW_DOWN);
 assert(stm32_switch_get_position(&_switch_defs[1])==SWITCH_HW_MID);
 a.IDR&=~(1U<<5); assert(stm32_switch_get_position(&_switch_defs[1])==SWITCH_HW_DOWN);
 a.IDR|=1U<<5; e.IDR&=~(1U<<15);
 assert(stm32_switch_get_position(&_switch_defs[1])==SWITCH_HW_UP);
 e.IDR&=~1U; // removed PE0 has no effect on SC
 assert(stm32_switch_get_position(&_switch_defs[2])==SWITCH_HW_UP);
 d.IDR&=~(1U<<11); assert(stm32_switch_get_position(&_switch_defs[2])==SWITCH_HW_DOWN);
 assert(stm32_switch_get_position(&_switch_defs[3])==SWITCH_HW_UP);
 e.IDR&=~(1U<<8); assert(stm32_switch_get_position(&_switch_defs[3])==SWITCH_HW_DOWN);
}
''')

    def test_actual_cli_debounce_gpio_states_pot_noise_logging_and_reconnect(self):
        source = (SRC / 'cli.cpp').read_text()
        monitors = 'static bool switchesWatch' + source.split(
            'static bool switchesWatch', 1)[1].split('static bool powerWatch', 1)[0]
        self.compile_run(f'#include "{TARGET / "button_monitor.h"}"\n'
                         f'#include "{TARGET / "gimbal_monitor.h"}"\n' + r'''
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
using gpio_t=unsigned;
#define GPIOA 1
#define GPIOC 3
#define GPIOD 4
#define GPIOE 5
#define GPIO_PIN(port,pin) ((port)*16+(pin))
#define DIM(a) (sizeof(a)/sizeof((a)[0]))
#define ADC_INPUT_FLEX 1
static bool cliSendCb=true;
static uint32_t ms;
static unsigned levels[96];
static uint16_t values[2]={2000,2000};
static std::vector<std::string> logs;
uint32_t time_get_ms() {return ms;}
unsigned gpio_read(unsigned pin) {assert(pin<96); return levels[pin];}
uint16_t adcGetInputValue(unsigned type,unsigned idx) {
 assert(type==ADC_INPUT_FLEX && idx<2); return values[idx];
}
void cliSerialPrint(const char* format, ...) {
 char text[128]; va_list args; va_start(args,format);
 int n=vsnprintf(text,sizeof(text),format,args); va_end(args);
 assert(n>=0 && n<int(sizeof(text))); logs.emplace_back(text);
}
void expect(const char* text) {assert(!logs.empty() && logs.back().find(text)!=std::string::npos);}
''' + monitors + r'''
int main() {
 for(auto& level:levels) level=1;
 pollSwitchMonitor(); assert(logs.size()==4); expect("SD(PE8) POS=UP GPIO=1");
 ms=10; levels[GPIO_PIN(GPIOC,13)]=0; pollSwitchMonitor(); assert(logs.size()==4);
 ms=39; pollSwitchMonitor(); assert(logs.size()==4);
 ms=40; pollSwitchMonitor(); expect("CHANGE SA(PC13) POS=DOWN GPIO=0");
 auto n=logs.size(); ms=100; pollSwitchMonitor(); assert(logs.size()==n);
 ms=110; levels[GPIO_PIN(GPIOE,15)]=0; pollSwitchMonitor();
 ms=140; pollSwitchMonitor(); expect("SB(PA5/PE15) POS=UP GPIO_H=1 GPIO_L=0");
 // A short bounce never becomes a reported position.
 n=logs.size(); ms=150; levels[GPIO_PIN(GPIOA,5)]=0; pollSwitchMonitor();
 ms=160; levels[GPIO_PIN(GPIOA,5)]=1; pollSwitchMonitor();
 ms=200; pollSwitchMonitor(); assert(logs.size()==n);
 ms=210; levels[GPIO_PIN(GPIOA,5)]=0; levels[GPIO_PIN(GPIOE,15)]=1; pollSwitchMonitor();
 ms=240; pollSwitchMonitor(); expect("SB(PA5/PE15) POS=DOWN GPIO_H=0 GPIO_L=1");
 ms=250; levels[GPIO_PIN(GPIOA,5)]=1; pollSwitchMonitor();
 ms=280; pollSwitchMonitor(); expect("SB(PA5/PE15) POS=MID GPIO_H=1 GPIO_L=1");
 n=logs.size(); levels[GPIO_PIN(GPIOE,0)]=0; levels[GPIO_PIN(GPIOE,7)]=0;
 ms=320; pollSwitchMonitor(); assert(logs.size()==n); // unused pins ignored
 ms=330; levels[GPIO_PIN(GPIOD,11)]=0; levels[GPIO_PIN(GPIOE,8)]=0; pollSwitchMonitor();
 ms=360; pollSwitchMonitor(); assert(logs.size()==n+2);
 assert(logs[n].find("SC(PD11) POS=DOWN")!=std::string::npos);
 expect("SD(PE8) POS=DOWN");
 ms=370; levels[GPIO_PIN(GPIOA,5)]=0; levels[GPIO_PIN(GPIOE,15)]=0; pollSwitchMonitor();
 ms=400; pollSwitchMonitor(); expect("POS=INVALID GPIO_H=0 GPIO_L=0");
 const char* swOff[]={"switches","off",nullptr}; assert(cliSwitches(swOff)==0);
 n=logs.size(); levels[GPIO_PIN(GPIOC,13)]=1; ms=500; pollSwitchMonitor(); assert(logs.size()==n);
 const char* swOn[]={"switches",nullptr}; assert(cliSwitches(swOn)==0);
 assert(logs.size()==n+5);
 cliSendCb=false; pollSwitchMonitor(); n=logs.size();
 cliSendCb=true; pollSwitchMonitor(); assert(logs.size()==n+4);
 logs.clear(); ms=1000; pollPotMonitor(); assert(logs.size()==2);
 expect("STATE S2(PA6/ADC1_IN6) adc=2000 delta=+0");
 values[1]+=8; ms=1050; pollPotMonitor(); assert(logs.size()==2);
 values[1]+=8; ms=1070; pollPotMonitor(); assert(logs.size()==2);
 ms=1100; pollPotMonitor(); expect("CHANGE S2(PA6/ADC1_IN6) adc=2016 delta=+16");
 values[0]-=32; ms=1150; pollPotMonitor(); expect("CHANGE S1(PB0/ADC1_IN8) adc=1968 delta=-32");
 n=logs.size(); ms=1200; pollPotMonitor(); assert(logs.size()==n);
 const char* potsOff[]={"pots","off",nullptr}; assert(cliPots(potsOff)==0);
 n=logs.size(); values[1]=4095; ms=1300; pollPotMonitor(); assert(logs.size()==n);
 const char* potsOn[]={"pots",nullptr}; assert(cliPots(potsOn)==0);
 assert(logs.size()==n+3); expect("STATE S2(PA6/ADC1_IN6) adc=4095 delta=+0");
 cliSendCb=false; pollPotMonitor(); values[1]=0; n=logs.size();
 cliSendCb=true; pollPotMonitor(); assert(logs.size()==n+2);
 expect("STATE S2(PA6/ADC1_IN6) adc=0 delta=+0");
 const char* bad[]={"switches","invalid",nullptr}; assert(cliSwitches(bad)==-1);
 assert(cliPots(bad)==-1);
}
''')
