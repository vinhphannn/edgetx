"""Monotonic flight-clock transitions and strict per-model config codec."""
from pathlib import Path
import shutil,subprocess,tempfile,unittest,os,sys
ROOT=Path(__file__).resolve().parents[3]

@unittest.skipUnless(shutil.which('g++'),'requires host g++')
class TyvorFlightTimerTests(unittest.TestCase):
    def run_cpp(self,body):
        with tempfile.TemporaryDirectory(prefix='tyvor-flight-clock-') as tmp:
            p=Path(tmp);(p/'test.cpp').write_text('#include "gui/128x64/tyvor_flight_timer.h"\n#include <cassert>\n#include <cstring>\n'+body)
            subprocess.run(['g++','-std=c++17','-fsanitize=undefined','-fno-sanitize-recover=all','-I',str(ROOT/'radio/src'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True)

    def test_arm_disarm_rearm_unknown_reset_and_model_restart(self):
        self.run_cpp(r'''
using S=TyvorArmState;
int main(){
 TyvorFlightClock c;c.clear(100);
 c.update(200,S::Armed);c.update(800,S::Armed);assert(!c.running&&!c.hasTime&&c.seconds()==0); // boot ON requires OFF first
 c.update(900,S::Disarmed);assert(c.ready&&c.hasTime);
 c.update(1000,S::Armed);assert(c.running&&c.seconds()==0);
 c.update(1123,S::Armed);c.update(1251,S::Armed);assert(c.elapsed==251&&c.seconds()==2);
 c.update(1300,S::Disarmed);assert(!c.running&&c.elapsed==300); // stop includes last known interval
 c.update(1500,S::Disarmed);assert(c.seconds()==3);
 c.update(1600,S::Armed);assert(c.running&&c.elapsed==0); // new flight
 c.update(1700,S::Armed);c.update(1800,S::Unknown);assert(c.elapsed==100);
 c.update(9000,S::Unknown);assert(c.elapsed==100);
 c.update(9100,S::Armed);assert(c.elapsed==100&&c.running); // reconnect, no reset or gap time
 c.update(9200,S::Armed);assert(c.elapsed==200);
 c.update(9300,S::Unknown);c.update(9400,S::Disarmed);assert(!c.running&&c.elapsed==200);
 c.update(9500,S::Armed);assert(c.elapsed==0&&c.running);
 c.clear(9600,true);c.update(9800,S::Armed);assert(c.hasTime&&!c.ready&&!c.running&&c.elapsed==0);
 c.update(9900,S::Disarmed);c.update(10000,S::Armed);c.update(10100,S::Armed);assert(c.seconds()==1);
 c.clear(10200);c.update(10300,S::Armed);assert(!c.hasTime&&!c.running); // model change / reboot
}
''')

    def test_tick_wrap_irregular_polling_and_saturation(self):
        self.run_cpp(r'''
int main(){
 TyvorFlightClock c;c.clear(UINT32_MAX-200);
 c.update(UINT32_MAX-190,TyvorArmState::Disarmed);c.update(UINT32_MAX-150,TyvorArmState::Armed);
 c.update(49,TyvorArmState::Armed);assert(c.elapsed==200&&c.seconds()==2);
 c.update(234,TyvorArmState::Armed);assert(c.elapsed==385);
 c.elapsed=UINT32_MAX-1;c.update(240,TyvorArmState::Armed);assert(c.elapsed==UINT32_MAX);
}
''')

    def test_config_roundtrip_rejects_corrupt_and_unsupported_values(self):
        self.run_cpp(r'''
int main(){
 TyvorFlightTimerConfig c;c.mode=TyvorFlightTimerMode::Switch;c.switchSource=-17;c.sensor=2;c.sensorId=65000;c.instance=3;c.subId=1;c.modules=7;c.verified=true;
 char text[64];tyvorEncodeFlightConfig(text,c);TyvorFlightTimerConfig d;assert(tyvorDecodeFlightConfig(text,d));
 assert(d.mode==c.mode&&d.switchSource==-17&&d.sensor==2&&d.sensorId==65000&&d.instance==3&&d.subId==1&&d.modules==7&&d.verified);
 const char* bad[]={"","2,0,0,0,0,0,0,0,0","1,2,0,0,0,0,0,0,0","1,0,-99999,0,0,0,0,0,0","1,0,0,256,0,0,0,0,0","1,0,0,0,0,0,0,0,2","1,0,0,0,0,0,0,0","1,0,0,0,0,0,0,0,0x","1,0,0,0,0,0,0,0,-1","1,0,0,0,0,0,0,0,0,"};
 for(auto s:bad)assert(!tyvorDecodeFlightConfig(s,d));
}
''')

class ActualFirmwareTimerTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('TYVOR_NATIVE_BUILD') and os.environ.get('TYVOR_UNIVERSAL_TIMER_TEST_OUTPUT'),'native integration paths required')
    def test_actual_firmware_sources(self):
        subprocess.run([sys.executable,str(Path(__file__).with_name('run_tyvor_universal_timer.py'))],check=True)
