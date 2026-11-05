"""V2 overlaps crystal startup with USB wait, preserving the backup domain."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SRC=Path(__file__).resolve().parents[2]/'src'


@unittest.skipUnless(shutil.which('g++'), 'requires host C++ compiler')
class RtcEarlyStartTests(unittest.TestCase):
    def test_early_hook_starts_lse_without_resetting_or_reselecting_rtc(self):
        text=(SRC/'boards/generic_stm32/bl_keys.cpp').read_text()
        start=text.index('void boardBLEarlyInit()')
        end=text.index('\n}',start)+2
        code=r'''
#include <cassert>
#include <cstdint>
struct Rcc {uint32_t AHB1ENR,APB1ENR,BDCR;};static Rcc rcc;
struct Port {uint32_t MODER,PUPDR;};static Port port;
struct Power {uint32_t CR;};static Power power;
#define RCC (&rcc)
#define GPIOC (&port)
#define PWR (&power)
constexpr uint32_t RCC_AHB1ENR_GPIOCEN=4,RCC_APB1ENR_PWREN=1U<<28;
constexpr uint32_t PWR_CR_DBP=1U<<8,RCC_BDCR_LSEON=1;
'''+text[start:end]+r'''
int main() {
 rcc.AHB1ENR=0x10;rcc.APB1ENR=0x42;rcc.BDCR=0x8100;power.CR=0x20;
 boardBLEarlyInit();
 assert(rcc.AHB1ENR==0x14);
#if defined(SAOLALINK_DEVEBOX_V2) && defined(RTCLOCK)
 assert(rcc.APB1ENR==(0x42|RCC_APB1ENR_PWREN));
 assert(power.CR==(0x20|PWR_CR_DBP));
 assert(rcc.BDCR==0x8101); // RTCEN and RTCSEL preserved, no backup reset
 boardBLEarlyInit();assert(rcc.BDCR==0x8101); // one-shot reset is harmless
#else
 assert(rcc.APB1ENR==0x42 && power.CR==0x20 && rcc.BDCR==0x8100);
#endif
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'test.cpp';source.write_text(code)
            for flags in ([],['-DSAOLALINK_DEVEBOX_V2'],
                          ['-DSAOLALINK_DEVEBOX_V2','-DRTCLOCK']):
                binary=Path(tmp)/'test'
                build=subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror',
                                      *flags,str(source),'-o',str(binary)],capture_output=True,text=True)
                self.assertEqual(build.returncode,0,build.stderr)
                subprocess.run([str(binary)],check=True,timeout=5)
