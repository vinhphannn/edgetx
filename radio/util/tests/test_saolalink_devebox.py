"""DevEBox ADC generation and CLI movement reporting, runnable on the host."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

RADIO = Path(__file__).resolve().parents[2]
SRC = RADIO / 'src'
TARGET = SRC / 'targets/taranis/saolalink_v1'
BASE = SRC / 'boards/hw_defs/saolalinkv1.json'


class DeveboxGimbalTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cmake'), 'requires cmake')
    def test_generated_channels_and_gpio_initialization_preserve_baseline(self):
        before = BASE.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'CMakeLists.txt').write_text(
                'cmake_minimum_required(VERSION 3.21)\nproject(adc_test NONE)\n'
                f'set(RADIO_SRC_DIR "{SRC}")\n'
                f'include("{TARGET / "adc_devebox.cmake"}")\n')
            subprocess.run(['cmake', '-S', str(root), '-B', str(root / 'build')],
                           check=True, capture_output=True, text=True)
            derived = root / 'build/saolalink-devebox-adc.json'
            expected = json.loads(before)
            for item in expected['adc_inputs']['inputs']:
                if item['name'] == 'RV':
                    item.update(gpio='GPIOC', pin='LL_GPIO_PIN_1', channel='LL_ADC_CHANNEL_11')
                elif item['name'] == 'RH':
                    item.update(gpio='GPIOC', pin='LL_GPIO_PIN_2', channel='LL_ADC_CHANNEL_12')
            self.assertEqual(json.loads(derived.read_text()), expected)
            generator = RADIO / 'util/hw_defs/generate_hw_def.py'
            template = RADIO / 'util/hw_defs/stm32_adc_inputs.jinja'
            rendered = subprocess.run(
                [sys.executable, str(generator), '-t', str(template), '-T', 'saolalinkv1', str(derived)],
                check=True, capture_output=True, text=True).stdout
            expected_pins = [('LH', 'GPIOA', 3, 3), ('LV', 'GPIOA', 2, 2),
                             ('RV', 'GPIOC', 1, 11), ('RH', 'GPIOC', 2, 12)]
            for name, port, pin, channel in expected_pins:
                self.assertRegex(rendered, rf'// {name}\s+// ADC_INPUT_STICK,\s+{port},\s+'
                                 rf'LL_GPIO_PIN_{pin},\s+LL_ADC_CHANNEL_{channel},')
            pins_a = re.search(r'_ADC_GPIOA_pins\[\] = \{(.*?)\};', rendered, re.S).group(1)
            pins_c = re.search(r'_ADC_GPIOC_pins\[\] = \{(.*?)\};', rendered, re.S).group(1)
            self.assertEqual(set(re.findall(r'LL_GPIO_PIN_(\d+)', pins_a)), {'2', '3'})
            self.assertEqual(set(re.findall(r'LL_GPIO_PIN_(\d+)', pins_c)), {'0', '1', '2'})
        self.assertEqual(BASE.read_bytes(), before)

    @unittest.skipUnless(shutil.which('g++'), 'requires g++')
    def test_reporting_noise_accumulated_motion_rate_limit_and_timer_wrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            harness = root / 'gimbal.cpp'
            harness.write_text(f'#include "{TARGET / "gimbal_monitor.h"}"\n' + r'''
#include <cassert>
int main() {
  DeveboxGimbalMonitor m;
  uint16_t v[4] = {2000, 2000, 2000, 2000};
  m.reset(v, 0);
  assert(m.update(v, 50) == 0); // stationary input stays quiet
  v[0] += 8; assert(m.update(v, 100) == 0); // small noise
  v[0] += 8; assert(m.update(v, 120) == 0); // rate limit
  assert(m.update(v, 150) == 1); // cumulative slow movement is retained
  assert(m.delta(0, v[0]) == 16);
  m.reported(0, v[0]);
  assert(m.update(v, 200) == 0); // no repeat while held
  v[1] -= 16; v[2] += 100; v[3] = 4095;
  assert(m.update(v, 250) == 14); // all other axes independently
  assert(m.delta(1, v[1]) == -16);
  for (unsigned i = 0; i < 4; ++i) m.reported(i, v[i]);
  assert(m.update(v, 300) == 0);
  v[3] = 0; assert(m.update(v, 350) == 8);
  assert(m.delta(3, v[3]) == -4095); // no unsigned underflow
  m.reset(v, 0xFFFFFFE0U); // reconnect / snapshot resets baseline
  v[2] += 16;
  assert(m.update(v, 0x10U) == 0);
  assert(m.update(v, 0x12U) == 4); // 50ms across tick rollover
}
''')
            subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            str(harness), '-o', str(root / 'gimbal')], check=True)
            subprocess.run([str(root / 'gimbal')], check=True)


class DeveboxPowerTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('g++'), 'requires g++')
    def test_real_driver_and_shutdown_boot_hold_short_press_usb_confirmation(self):
        source = (SRC / 'edgetx.cpp').read_text()
        delay_from_yaml = source.split('int pwrDelayFromYaml(int delay)\n{', 1)[1].split('\n}', 1)[0]
        delay_time = source.split('uint32_t pwrDelayTime(int delay)\n{', 1)[1].split('\n}', 1)[0]
        power_check = source.split('static bool pwrUsbNeedsConfirmation()', 1)[1].split(
            '\n#else\nuint32_t pwrCheck()', 1)[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'hal').mkdir()
            (root / 'os').mkdir()
            for name in ['hal/abnormal_reboot.h', 'hal/gpio.h', 'hal/usb_driver.h', 'stm32_gpio.h']:
                (root / name).write_text('')
            (root / 'os/time.h').write_text('#include <stdint.h>\nuint32_t time_get_ms();\n')
            (root / 'board.h').write_text(r'''
#pragma once
#include <stdint.h>
#define SAOLALINK_DEVEBOX
#define PWR_BUTTON_PRESS
#define GPIO_PIN(port,pin) ((port)|(pin))
#define GPIOD 0x40020C00U
#define GPIOB 0x40020400U
#define GPIO_IN 0
#define GPIO_IN_PU 1
#define GPIO_OUT 2
#define GPIO_PIN_SPEED_LOW 0
#define WAS_RESET_BY_WATCHDOG_OR_SOFTWARE() false
void gpio_init(unsigned, int, int);
void gpio_set(unsigned);
void gpio_clear(unsigned);
int gpio_read(unsigned);
void pwrOn();
''' + f'#include "{TARGET / "hal_overrides.h"}"\n')
            harness = root / 'power.cpp'
            # Redirect the driver's same-directory STM32 header to host GPIO mocks.
            driver = (SRC / 'targets/common/arm/stm32/pwr_driver.cpp').read_text().replace(
                '#include "stm32_gpio.h"', '#include <stm32_gpio.h>')
            harness.write_text('#include <cassert>\n#include <cstring>\n#include <vector>\n'
                + driver + '\n' + r'''
static uint32_t ms;
static bool hold, rawPressed, usbConfigured;
static int confirmations;
static std::vector<unsigned> initialized;
uint32_t time_get_ms() {return ms;}
void gpio_init(unsigned pin, int mode, int) {
  assert(pin==PWR_ON_GPIO || pin==PWR_SWITCH_GPIO || pin==SAOLALINK_RF_BOOT_GPIO);
  assert(mode==(pin==PWR_ON_GPIO ? GPIO_OUT : pin==PWR_SWITCH_GPIO ? GPIO_IN_PU : GPIO_IN));
  initialized.push_back(pin);
}
void gpio_set(unsigned pin) {assert(pin==PWR_ON_GPIO); hold=true;}
void gpio_clear(unsigned pin) {assert(pin==PWR_ON_GPIO); hold=false;}
int gpio_read(unsigned pin) {
  if(pin==PWR_SWITCH_GPIO) return !rawPressed;
  assert(pin==PWR_ON_GPIO); return hold;
}
bool deveboxUsbConfigured() {return usbConfigured;}
bool usbPlugged() {return true;} // old development fallback must not force a popup
using tmr10ms_t = uint32_t;
using event_t = unsigned;
enum {e_power_on, e_power_press, e_power_off, e_backlight_mode_off};
struct {int pwrOffSpeed=0; int backlightMode=0; bool disableRssiPoweroffAlarm=false;
        bool disableTrainerPoweroffAlarm=false;} g_eeGeneral;
uint32_t get_tmr10ms() {return ms/10;}
int pwrDelayFromYaml(int delay) {
''' + delay_from_yaml + '\n}\nuint32_t pwrDelayTime(int delay) {\n' + delay_time + r'''
}
bool pwrDelayHoldActive() {return pwrPressed();}
uint32_t PWR_PRESS_SHUTDOWN_DELAY() {return pwrDelayTime(g_eeGeneral.pwrOffSpeed);}
uint32_t pwr_press_time;
uint32_t pwrPressedDuration() {return pwr_press_time ? get_tmr10ms()-pwr_press_time : 0;}
bool pwrOffDueToInactivity() {return false;}
enum class ActivitySource {Keys};
void inactivityTimerReset(ActivitySource) {}
bool isTrainerConnected() {return false;}
void audioEvent(int) {}
void lcdRefreshWait() {}
void lcdClear() {}
void lcdRefresh() {}
event_t getEvent() {return 0;}
void drawShutdownAnimation(uint32_t, uint32_t, const char*) {}
bool warningResult=true; // simulate ENTER when the USB popup is presented
const char* warningText=nullptr;
#define TELEMETRY_STREAMING() false
#define AU_MODEL_STILL_POWERED 0
#define STR_MODEL_STILL_POWERED "model"
#define STR_MODEL_SHUTDOWN "shutdown"
#define STR_USB_STILL_CONNECTED "USB"
#define STR_TRAINER_STILL_CONNECTED "trainer"
#define BACKLIGHT_ENABLE() ((void)0)
#define POPUP_CONFIRMATION(a,b) (++confirmations)
#define SET_WARNING_INFO(a,b,c) ((void)0)
#define DISPLAY_WARNING(a) ((void)0)
#define LED_ERROR_BEGIN() ((void)0)
#define LED_ERROR_END() ((void)0)
#define WDG_RESET() ((void)0)
static bool pwrUsbNeedsConfirmation()
''' + power_check + r'''
int main(int argc, char**) {
  static_assert(PWR_ON_GPIO==(GPIOD|0));
  static_assert(PWR_SWITCH_GPIO==(GPIOD|1));
  assert(pwrDelayTime(0)==200); // units are 10ms ticks: default is 2 seconds
  usbConfigured = argc>1;
  rawPressed=true;
  pwrInit();
  assert(hold && initialized.size()==3);
  assert(initialized[0]==PWR_ON_GPIO && initialized[1]==SAOLALINK_RF_BOOT_GPIO && initialized[2]==PWR_SWITCH_GPIO);
  for(ms=0;ms<10000;ms+=20) assert(pwrCheck()==e_power_on); // boot press ignored
  rawPressed=false;
  for(unsigned i=0;i<10;++i,ms+=20) assert(pwrCheck()==e_power_on);
  rawPressed=true;
  for(unsigned i=0;i<6;++i,ms+=20) assert(pwrCheck()!=e_power_off); // short press
  rawPressed=false;
  for(unsigned i=0;i<10;++i,ms+=20) assert(pwrCheck()!=e_power_off);
  rawPressed=true;
  unsigned result=e_power_on;
  for(unsigned i=0;i<120;++i,ms+=20) result=pwrCheck();
  assert(result==e_power_off && hold); // shutdown request does not drop HOLD early
  assert(confirmations==(usbConfigured ? 1 : 0));
  rawPressed=false;
  (void)pwrPressed(); ms+=40;
  assert(!pwrPressed());
  pwrOff(); assert(!hold);
}
''')
            compiled = subprocess.run(['g++', '-std=c++17', '-I', str(root),
                                       '-I', str(SRC), str(harness), '-o', str(root / 'power')],
                                      capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            subprocess.run([str(root / 'power')], check=True)
            subprocess.run([str(root / 'power'), 'usb'], check=True)

    @unittest.skipUnless(shutil.which('g++'), 'requires g++')
    def test_power_button_release_bounce_and_tick_wrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            harness = root / 'button.cpp'
            harness.write_text(f'#include "{TARGET / "power_button.h"}"\n#include <cassert>\n' + r'''
int main() {
  DeveboxPowerButton b;
  assert(!b.update(true, 0)); assert(!b.update(true, 10000)); // boot hold
  assert(!b.update(false, 10001)); assert(!b.update(true, 10020)); // release bounce
  assert(!b.update(true, 10060)); // not armed by brief release
  assert(!b.update(false, 10061)); assert(!b.update(false, 10091)); // arm
  assert(!b.update(true, 10100)); assert(!b.update(false, 10110)); // press bounce
  assert(!b.update(true, 10120)); assert(!b.update(true, 10149));
  assert(b.update(true, 10150));
  assert(b.update(false, 10200)); assert(!b.update(false, 10230));
  b.reset();
  assert(!b.update(false, 0xFFFFFFC0U)); assert(!b.update(false, 0xFFFFFFDEU));
  assert(!b.update(true, 0xFFFFFFF0U)); assert(b.update(true, 0xEU)); // wrap
}
''')
            subprocess.run(['g++', '-std=c++17', str(harness), '-o', str(root / 'button')], check=True)
            subprocess.run([str(root / 'button')], check=True)


if __name__ == '__main__':
    unittest.main()
