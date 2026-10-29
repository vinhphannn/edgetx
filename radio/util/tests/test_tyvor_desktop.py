"""Native simulator hold/axis/settings checks; no hardware power or mixer edits."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SIMU = ROOT/'radio/src/targets/simu'

@unittest.skipUnless(shutil.which('g++'), 'requires host g++')
class DesktopControlsTests(unittest.TestCase):
    def test_hold_cancel_two_seconds_and_tick_wrap(self):
        code = f'#include "{SIMU}/desktop_controls.h"\n#include <cassert>\n' + r'''
int main() {
 DesktopPowerHold p;
 p.pressed=true; assert(p.poll(10)==DesktopPowerHold::On); // opt-in only
 p.enabled=true;
 assert(p.poll(20)==DesktopPowerHold::Press);
 assert(p.poll(219)==DesktopPowerHold::Press&&p.progress==199);
 p.pressed=false;assert(p.poll(220)==DesktopPowerHold::On&&p.progress==0);
 p.pressed=true;assert(p.poll(300)==DesktopPowerHold::Press);
 assert(p.poll(499)==DesktopPowerHold::Press);
 assert(p.poll(500)==DesktopPowerHold::Off&&p.progress==200);
 p.pressed=false;p.poll(501);p.pressed=true;
 assert(p.poll(0xfffffff0)==DesktopPowerHold::Press);
 assert(p.poll(0xb7)==DesktopPowerHold::Press);
 assert(p.poll(0xb8)==DesktopPowerHold::Off);
}
'''
        self.compile_run(code)

    def test_named_physical_axes_sign_range_and_mode_one_to_four(self):
        code = f'#include "{SIMU}/desktop_controls.h"\n#include <cassert>\n' + r'''
int main() {
 for(unsigned mode=0;mode<4;++mode)assert(desktopThrottleOnLeft(mode)==(mode==1||mode==3));
 const char* names[]={"LH","LV","RV","RH"};
 for(unsigned axis=0;axis<4;++axis) for(unsigned n=0;n<=4;++n) {
  float pos[]={.5f,.5f,.5f,.5f};pos[axis]=n/4.f;
  for(unsigned input=0;input<4;++input) {
   uint16_t value=0;assert(desktopMainAxis(names[input],pos[0],pos[1],pos[2],pos[3],value));
   float expected=input==0?pos[0]:input==1?1-pos[1]:input==2?1-pos[3]:pos[2];
   assert(value==uint16_t(expected*4096));
  }
 }
 uint16_t v=999;
 assert(!desktopMainAxis("unrelated",0,0,0,0,v)&&v==999);
 desktopMainAxis("LH",-1,0,0,0,v);assert(v==0);
 desktopMainAxis("RH",0,0,2,0,v);assert(v==4096);
}
'''
        self.compile_run(code)

    def test_settings_argument_controls_initial_throttle_side(self):
        source=(SIMU/'sdl_simu.cpp').read_text()
        start=source.index('int find_input_mode(')
        end=source.index('\nint main(',start)
        code=r'''
#include <filesystem>
#include <fstream>
#include <regex>
#include <string>
#include <cassert>
int default_input_mode() {return 0;}
'''+source[start:end]+r'''
int main() {
 std::filesystem::create_directories("user settings/RADIO");
 std::filesystem::create_directories("RADIO");
 std::ofstream("RADIO/radio.yml")<<"stickMode: 0\n";
 for(int mode=0;mode<4;++mode) {
  std::ofstream("user settings/RADIO/radio.yml")<<"stickMode: "<<mode<<"\n";
  assert(find_input_mode("user settings")==mode);
 }
 assert(find_input_mode("missing")==0);
 for(const char* invalid:{"4","99999999999999999999999999"}) {
  std::ofstream("user settings/RADIO/radio.yml")<<"stickMode: "<<invalid<<"\n";
  assert(find_input_mode("user settings")==0);
 }
}
'''
        self.compile_run(code)

    def compile_run(self, source):
        with tempfile.TemporaryDirectory(prefix='tyvor-desktop-') as folder:
            root=Path(folder);cpp=root/'check.cpp';cpp.write_text(source)
            subprocess.run(['g++','-std=c++17','-Wall','-Wextra',str(cpp),'-o',str(root/'check')],check=True,capture_output=True,text=True)
            subprocess.run([str(root/'check')],cwd=root,check=True)

if __name__=='__main__':unittest.main()
