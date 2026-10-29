"""HOME-only mode label, RF bars and actual sensor/renderer integration."""
from pathlib import Path
import os,shutil,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]

@unittest.skipUnless(shutil.which('g++'),'requires host g++')
class HomeRfUiTests(unittest.TestCase):
    def cpp(self,body):
        with tempfile.TemporaryDirectory(prefix='tyvor-home-rf-') as tmp:
            p=Path(tmp);(p/'test.cpp').write_text('#include "gui/128x64/tyvor_flight_data.h"\n#include <cassert>\n#include <cstring>\n#include <initializer_list>\n'+body)
            subprocess.run(['g++','-std=c++17','-fsanitize=undefined','-fno-sanitize-recover=all','-I',str(ROOT/'radio/src'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True)

    def test_mode_copy_and_rf_quantization_preserve_original_inputs(self):
        self.cpp(r'''
int main(){
 char out[17];
 for(auto raw:{"STAB*","AIR*","!FS!*","RTH*"}){char original[17];strcpy(original,raw);tyvorHomeModeLabel(original,out);assert(strlen(out)==strlen(raw)-1&&!memcmp(out,raw,strlen(out)));assert(!strcmp(original,raw));}
 for(auto raw:{"AIR!","AIR?","!FS!","A*B","*","AIR**","STAB","ABCDEFGHIJKLMNOP"}){tyvorHomeModeLabel(raw,out);assert(!strcmp(raw,out));}
 TyvorFlightData d;assert(tyvorHomeLinkBars(d)==-1);d.linkQualityValid=true;
 for(unsigned q=0;q<=100;++q){d.linkQuality=q;assert(tyvorHomeLinkBars(d)==int(q*5+50)/100);}
 d.linkQuality=0;assert(tyvorHomeLinkBars(d)==0);d.linkQuality=25;assert(tyvorHomeLinkBars(d)==1);d.linkQuality=50;assert(tyvorHomeLinkBars(d)==3);d.linkQuality=75;assert(tyvorHomeLinkBars(d)==4);d.linkQuality=100;assert(tyvorHomeLinkBars(d)==5);d.linkQuality=101;assert(tyvorHomeLinkBars(d)==-1);
}
''')

    def test_rf_icon_pixels_stay_in_original_label_slot(self):
        source=(ROOT/'radio/src/gui/128x64/view_main.cpp').read_text();a=source.index('static void drawTyvorLinkQuality(');b=source.index('{',a)+1;depth=1
        while depth:depth+=(source[b]=='{')-(source[b]=='}');b+=1
        self.cpp(r'''
using coord_t=int;constexpr int FORCE=1,SMLSIZE=2;bool pixels[64][128];bool question=false;
void lcdDrawText(int x,int y,const char*s,int f){assert(x==52&&y==17&&f==SMLSIZE&&!strcmp(s,"?"));question=true;}
void lcdDrawSolidFilledRect(int x,int y,int w,int h,int f){assert(x>=46&&x+w<=65&&y>=17&&y+h<=23&&f==FORCE);for(int j=y;j<y+h;j++)for(int i=x;i<x+w;i++)pixels[j][i]=true;}
'''+source[a:b]+r'''
int main(){
 for(int bars=-1;bars<=5;++bars){
  memset(pixels,0,sizeof(pixels));question=false;drawTyvorLinkQuality(46,17,bars);assert(question==(bars<0));
  for(int i=0;i<5;++i){int n=0;for(int y=17;y<23;++y)for(int x=46+4*i;x<49+4*i;++x)n+=pixels[y][x];assert(n==(i<bars?3*(i+2):0));}
 }
}
''')

class ActualHomeRfUiTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('TYVOR_NATIVE_BUILD') and os.environ.get('TYVOR_HOME_RF_TEST_OUTPUT'),'native integration paths required')
    def test_actual_rf_mode_and_arm_pipeline(self):
        subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('run_tyvor_home_rf_ui.py'))],check=True)
