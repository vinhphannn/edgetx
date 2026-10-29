"""SATS and explicitly relative CRSF 0x09 altitude, without GPS/TX fallback."""
from pathlib import Path
import os,shutil,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]

@unittest.skipUnless(shutil.which('g++'),'requires host g++')
class HomeAltitudeTests(unittest.TestCase):
    def test_whole_metre_scale_signed_bounds_and_count_format(self):
        code=r'''
#include "gui/128x64/tyvor_flight_data.h"
#include <cassert>
#include <cstring>
#include <initializer_list>
int main(){
 for(int precision=0,scale=1;precision<=3;++precision,scale*=10){
  for(int value:{0,12,-3,125,-1000,32766}){int32_t meters;assert(tyvorFlightAltitudeMeters(value*scale,precision,meters)&&meters==value);}
  int32_t meters;assert(!tyvorFlightAltitudeMeters(-1000*scale-1,precision,meters));assert(!tyvorFlightAltitudeMeters(32766*scale+1,precision,meters));
 }
 int32_t meters;assert(!tyvorFlightAltitudeMeters(INT32_MIN,2,meters));assert(!tyvorFlightAltitudeMeters(INT32_MAX,2,meters));assert(!tyvorFlightAltitudeMeters(0,4,meters));assert(tyvorFlightAltitudeMeters(-345,2,meters)&&meters==-3);
 TyvorFlightData d;char text[16];tyvorFlightSatsText(text,d);assert(!strcmp(text,"--"));tyvorFlightAltitudeText(text,d);assert(!strcmp(text,"--"));
 d.satellitesValid=true;for(int value:{0,8,12,18,255}){d.satellites=value;tyvorFlightSatsText(text,d);char expected[16];snprintf(expected,sizeof(expected),"%d",value);assert(!strcmp(text,expected));}
 d.altitudeValid=true;for(int value:{0,12,-3,125,-1000,32766}){d.altitudeMeters=value;tyvorFlightAltitudeText(text,d);char expected[16];snprintf(expected,sizeof(expected),"%dm",value);assert(!strcmp(text,expected));}
 d.altitudeMeters=INT32_MAX;tyvorFlightAltitudeText(text,d);assert(!strcmp(text,"--"));d.altitudeMeters=INT32_MIN;tyvorFlightAltitudeText(text,d);assert(!strcmp(text,"--"));
 d.altitudeValid=false;d.powerValid=true;d.power=10;tyvorFlightAltitudeText(text,d);assert(!strcmp(text,"--"));
}
'''
        with tempfile.TemporaryDirectory(prefix='tyvor-sats-alt-') as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(code)
            subprocess.run(['g++','-std=c++17','-fsanitize=undefined','-fno-sanitize-recover=all','-I',str(ROOT/'radio/src'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True)

class ActualAltitudePipelineTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('TYVOR_NATIVE_BUILD') and os.environ.get('TYVOR_ALT_TEST_OUTPUT'),'native integration paths required')
    def test_actual_crsf_sensor_scale_reference_and_home(self):
        subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('run_tyvor_home_altitude.py'))],check=True)
