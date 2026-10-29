"""Release-scoped Betaflight decoder, persisted profile, and actual firmware pipeline."""
from pathlib import Path
import os,shutil,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]

@unittest.skipUnless(shutil.which('g++'),'requires host g++')
class BetaflightArmDecoderTests(unittest.TestCase):
    def cpp(self,body):
        with tempfile.TemporaryDirectory(prefix='tyvor-bf455-') as tmp:
            p=Path(tmp);(p/'test.cpp').write_text('#include "gui/128x64/tyvor_fc_arm.h"\n#include <cassert>\n'+body)
            subprocess.run(['g++','-std=c++17','-fsanitize=undefined','-fno-sanitize-recover=all','-I',str(ROOT/'radio/src'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True)

    def test_exact_release_modes_suffixes_failsafe_and_invalid_text(self):
        self.cpp(r'''
int main(){
 using P=TyvorFcArmProfile;using S=TyvorArmState;
 for(auto text:{"ACRO","RTH","MANU","STAB","HOR","AIR"}){
  assert(tyvorDecodeFcArm(P::Betaflight455,text,16)==S::Armed);
  char d[16];snprintf(d,sizeof(d),"%s*",text);
  assert(tyvorDecodeFcArm(P::Betaflight455,d,sizeof(d))==S::Disarmed);
  assert(tyvorDecodeFcArm(P::Unconfigured,d,sizeof(d))==S::Unknown);
 }
 assert(tyvorDecodeFcArm(P::Betaflight455,"WAIT*",16)==S::Disarmed);
 for(auto text:{"","*","WAIT","AIR!","AIR?","ACRO!","ACRO?","!FS!","!FS!*","!ERR*","ANGL","ANGL*","AIR**","AIR* "," AIR*","air*","AIR\n","AIRx","ARMED","DISARMED"})
  assert(tyvorDecodeFcArm(P::Betaflight455,text,strlen(text)+1)==S::Unknown);
 const char unterminated[]={'A','I','R'};
 assert(tyvorDecodeFcArm(P::Betaflight455,unterminated,sizeof(unterminated))==S::Unknown);
 assert(tyvorDecodeFcArm(P::Betaflight455,"AIR*",4)==S::Unknown);
 assert(tyvorDecodeFcArm(P::Betaflight455,nullptr,16)==S::Unknown);
 assert(tyvorDecodeFcArm(P(99),"AIR*",16)==S::Unknown);
}
''')

    def test_profile_codec_is_strict_and_model_scoped(self):
        self.cpp(r'''
int main(){
 TyvorFcArmConfig c;c.profile=TyvorFcArmProfile::Betaflight455;c.sensor=40;c.modules=1285;c.verified=true;
 char text[40];tyvorEncodeFcArmConfig(text,c);assert(!strcmp(text,"1,1,40,1285,1"));
 TyvorFcArmConfig result;assert(tyvorDecodeFcArmConfig(text,result));
 assert(result.profile==c.profile&&result.sensor==40&&result.modules==1285&&result.verified);
 for(auto bad:{"","1","2,1,1,5,1","1,2,1,5,1","1,-1,1,5,1","1,1,256,5,1","1,1,1,65536,1","1,1,1,5,2","1,1,1,5,1junk","1,1,1,5,1,0","1,1,1,5,","1,1,1,5,9999999999999"})
  assert(!tyvorDecodeFcArmConfig(bad,result));
 assert(!tyvorDecodeFcArmConfig(nullptr,result));
}
''')

class ActualBetaflightPipelineTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('TYVOR_NATIVE_BUILD') and os.environ.get('TYVOR_BF455_TEST_OUTPUT'),'native integration paths required')
    def test_actual_crsf_fm_provider_home_and_switch_timer(self):
        subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('run_tyvor_betaflight_arm.py'))],check=True)
