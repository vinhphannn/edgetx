"""Execute menu visibility/navigation without disabling shared trainer/PPM code."""
from pathlib import Path
import shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
SRC=ROOT/'radio/src'

def function(s,name):
 a=s.index(name);b=s.index('{',a)+1;depth=1
 while depth:depth+=(s[b]=='{')-(s[b]=='}');b+=1
 return s[a:b]+'\n'

@unittest.skipUnless(shutil.which('g++'),'requires host C++ compiler')
class TyvorMenusTests(unittest.TestCase):
 def run_cpp(self,code,defines=()):
  with tempfile.TemporaryDirectory(prefix='tyvor-menu-') as temp:
   p=Path(temp);(p/'check.cpp').write_text(code)
   out=subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-fsanitize=undefined','-fno-sanitize-recover=all','-I',str(SRC),*['-D'+d for d in defines],str(p/'check.cpp'),'-o',str(p/'check')],capture_output=True,text=True)
   self.assertEqual(out.returncode,0,out.stderr)
   out=subprocess.run([str(p/'check')],capture_output=True,text=True);self.assertEqual(out.returncode,0,out.stderr)

 def test_real_page_table_and_navigation_wrap_skip_only_trainer_on_tyvor(self):
  source=(SRC/'gui/common/stdlcd/menu_radio.cpp').read_text();array=source[source.index('const MenuHandler menuTabGeneral'):];array=array[:array.index('};')+2]
  indexes=(SRC/'gui/common/stdlcd/menus_common.h').read_text();a=indexes.index('enum MenuRadioIndexes');indexes=indexes[a:indexes.index('};',a)+2]
  nav=(SRC/'gui/navigation/navigation.cpp').read_text()
  code=r'''
#include <cstdint>
#include <cassert>
#include <vector>
#define RADIO_TOOLS
constexpr uint8_t HIDDEN_ROW=0xfe;
bool trainer=true,gf=true;unsigned trainerQueries=0;
bool radioTrainerEnabled(){++trainerQueries;return trainer;}
bool radioGFEnabled(){return gf;}
#include "gui/128x64/tyvor_menu.h"
using Fn=void(*)(uint16_t);
struct MenuHandler{Fn menuFunc;bool(*enabled)();bool isEnabled()const{return !enabled||enabled();}};
void menuRadioTools(uint16_t){}void menuRadioSdManager(uint16_t){}void menuRadioSetup(uint16_t){}
void menuRadioSpecialFunctions(uint16_t){}void menuRadioTrainer(uint16_t){}void menuRadioHardware(uint16_t){}void menuRadioVersion(uint16_t){}
'''+indexes+'\n'+array+'\n'+''.join(function(nav,s) for s in ['uint8_t chgMenu(','uint8_t menuSize(','uint8_t menuIdx('])+r'''
int main(){
 static_assert(MENU_RADIO_PAGES_COUNT==7&&MENU_RADIO_TRAINER==4,"keep menu indexes stable");
 for(bool visible:{false,true})for(bool globalFn:{false,true}){
  trainer=visible;gf=globalFn;const auto before=trainerQueries;
#if defined(TYVOR_HIDE_TRAINER)
  const bool expected=false;assert(tyvorTrainerRow(3)==HIDDEN_ROW);
#else
  const bool expected=visible;assert(tyvorTrainerRow(3)==3);
#endif
  assert(menuTabGeneral[MENU_RADIO_TRAINER].isEnabled()==expected);
#if defined(TYVOR_HIDE_TRAINER)
  assert(trainerQueries==before); // no control/configuration read or write
#else
  assert(trainerQueries==before+1);
#endif
  assert(trainer==visible&&gf==globalFn);
  const int count=5+int(globalFn)+int(expected);assert(menuSize(menuTabGeneral,7)==count);
  for(int dir:{-1,1}){
   uint8_t at=0;std::vector<int> visited;
   for(int i=0;i<count;i++){at=chgMenu(at,menuTabGeneral,7,dir);assert(menuTabGeneral[at].isEnabled());visited.push_back(at);}
   assert(at==0);
   for(int i=0;i<count;i++)for(int j=i+1;j<count;j++)assert(visited[i]!=visited[j]);
   if(!expected)for(int page:visited)assert(page!=MENU_RADIO_TRAINER);
  }
  assert(chgMenu(MENU_RADIO_TRAINER,menuTabGeneral,7,1)==MENU_RADIO_HARDWARE);
 }
}
'''
  for defines in [('RADIO_SAOLALINKV1','LCD_W=128'),('RADIO_SAOLALINKV1','LCD_W=212'),('LCD_W=128',)]:
   with self.subTest(defines=defines):self.run_cpp(code,defines)

 def test_actual_radio_and_model_rows_hide_trainer_without_hiding_rssi_alarm(self):
  radio=(SRC/'gui/128x64/radio_setup.cpp').read_text();model=(SRC/'gui/128x64/model_setup.cpp').read_text()
  alarms=radio.split('    // Alarms\n',1)[1].split('    // Backlight',1)[0]
  def view_rows(s):return s.split('     VIEWOPT_ROW(LABEL(RadioMenuTabs)),',1)[1].split('     VIEWOPT_ROW(LABEL(ModelMenuTabs)),',1)[0]
  code=r'''
#include <cstdint>
#include <cassert>
constexpr uint8_t HIDDEN_ROW=0xfe;
bool radioTrainerEnabled(){return true;}
#include "gui/128x64/tyvor_menu.h"
#define ALARMS_ROW(x) (x)
#define VIEWOPT_ROW(x) (x)
'''+f'uint8_t alarms[]={{{alarms}}};\nuint8_t radioView[]={{{view_rows(radio)}}};\nuint8_t modelView[]={{{view_rows(model)}}};\n'+r'''
int main(){
 static_assert(sizeof(alarms)==7&&sizeof(radioView)==2&&sizeof(modelView)==2,"row counts/indices stable");
 for(int i=0;i<6;i++)assert(alarms[i]==0); // battery, inactivity, memory, alarms, RSSI stay visible
#if defined(TYVOR_HIDE_TRAINER)
 assert(alarms[6]==HIDDEN_ROW&&radioView[1]==HIDDEN_ROW&&modelView[1]==HIDDEN_ROW);
#else
 assert(alarms[6]==0&&radioView[1]==0&&modelView[1]==0);
#endif
 assert(radioView[0]==0&&modelView[0]==0); // global functions unaffected
}
'''
  self.run_cpp(code,('RADIO_SAOLALINKV1','LCD_W=128'));self.run_cpp(code,('LCD_W=128',))

 def test_model_trainer_section_keeps_four_or_five_hidden_slots(self):
  s=(SRC/'gui/128x64/model_setup.cpp').read_text();a=s.index('#if defined(TYVOR_HIDE_TRAINER)');b=s.index('#elif defined(PCBX7ACCESS)',a);section=s[a:b]+'#endif\n'
  code=r'''
#include <cstdint>
#include <cassert>
constexpr uint8_t HIDDEN_ROW=0xfe;
bool radioTrainerEnabled(){return true;}
#include "gui/128x64/tyvor_menu.h"
'''+section+r'''
uint8_t rows[]={TRAINER_ROWS};
int main(){
#ifdef BLUETOOTH
 static_assert(sizeof(rows)==5,"preserve Bluetooth slot");
#else
 static_assert(sizeof(rows)==4,"preserve PPM slots");
#endif
 for(auto r:rows)assert(r==HIDDEN_ROW);
}
'''
  for extra in [(),('BLUETOOTH',)]:self.run_cpp(code,('RADIO_SAOLALINKV1','LCD_W=128',*extra))

if __name__=='__main__':unittest.main()
