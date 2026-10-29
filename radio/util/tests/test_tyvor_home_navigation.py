"""Execute the real HOME event dispatcher for TYVOR and legacy radio profiles."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(shutil.which('g++'), 'requires host g++')
class TyvorHomeNavigationTests(unittest.TestCase):
    def test_single_home_saved_views_shortcuts_and_unaffected_radios(self):
        text = (ROOT/'radio/src/gui/128x64/view_main.cpp').read_text()
        start = text.index('void menuMainView(event_t event)')
        end = text.index('#if defined(TYVOR_HOME)\n  // HOME navigation', start)
        # Execute the complete production event switch, then observe the view
        # handed to rendering. Rendering itself has separate pixel/layout tests.
        dispatcher = text[start:end] + ' renderedView=view; renderedBase=view_base;\n}\n'
        code = r'''
#include <cassert>
#include <cstdint>
#include <cstring>
using event_t=uint16_t;
#define EVT_KEY_NEXT_PAGE 2
#define EVT_KEY_PREVIOUS_PAGE 3
#define EVT_KEY_CONTEXT_MENU 4
#define EVT_KEY_LAST_MENU 5
#define EVT_KEY_MODEL_MENU 6
#define EVT_KEY_GENERAL_MENU 7
#define EVT_KEY_NEXT_VIEW 8
#if defined(TEST_PREVIOUS_VIEW)
#define EVT_KEY_PREVIOUS_VIEW 9
#endif
#define EVT_KEY_STATISTICS 10
#define EVT_KEY_TELEMETRY 11
#define EVT_KEY_FIRST(k) (100+(k))
constexpr int EVT_ENTRY=1,KEY_EXIT=1,KEY_UP=2,KEY_DOWN=3,EE_GENERAL=1;
enum {VIEW_OUTPUTS_VALUES,VIEW_OUTPUTS_BARS,VIEW_INPUTS,VIEW_TIMER2,VIEW_CHAN_MONITOR,VIEW_COUNT};
constexpr uint8_t ALTERNATE_VIEW=16;
struct { uint8_t view; uint32_t guard=0x12345678; } g_eeGeneral;
unsigned dirty=0,popup=0,killed=0;uint8_t renderedView=255,renderedBase=255;
using Handler=void(*)(event_t);Handler pushed=nullptr,chained=nullptr;
void menuModelSelect(event_t){} void menuRadioTools(event_t){}
void menuStatisticsView(event_t){} void menuViewTelemetry(event_t){}
struct {Handler menuFunc;} menuTabGeneral[]={{menuRadioTools}};
Handler lastPopMenu(){return menuModelSelect;}
void pushMenu(Handler h){pushed=h;}void chainMenu(Handler h){chained=h;}
void killEvents(int){++killed;}void storageDirty(int){++dirty;}
bool modelHasNotes(){return true;}
constexpr int STR_VIEW_NOTES=1,STR_RESET_SUBMENU=2,STR_STATISTICS=3,STR_ABOUT_US=4;
#define POPUP_MENU_ADD_ITEM(...) (++popup)
#define POPUP_MENU_START(...) (++popup)
'''+dispatcher+r'''
int main(){
#if defined(TYVOR_HOME)
 for(unsigned saved=0;saved<256;++saved){
  g_eeGeneral.view=saved;auto before=g_eeGeneral;
  for(unsigned repeat=0;repeat<12;++repeat){
   for(auto event:{EVT_KEY_NEXT_PAGE,EVT_KEY_PREVIOUS_PAGE,EVT_KEY_NEXT_VIEW
#if defined(TEST_PREVIOUS_VIEW)
    ,EVT_KEY_PREVIOUS_VIEW
#endif
   }){
    menuMainView(event);assert(g_eeGeneral.view==saved&&g_eeGeneral.guard==before.guard);
    assert(renderedView==VIEW_OUTPUTS_VALUES&&renderedBase==VIEW_OUTPUTS_VALUES);
    assert(!dirty&&!pushed&&!chained);
   }
  }
  menuMainView(EVT_ENTRY);assert(renderedView==VIEW_OUTPUTS_VALUES&&g_eeGeneral.view==saved);
 }
#else
 g_eeGeneral.view=0;menuMainView(EVT_KEY_NEXT_PAGE);assert(g_eeGeneral.view==16);
 menuMainView(EVT_KEY_PREVIOUS_PAGE);assert(g_eeGeneral.view==0);
 menuMainView(EVT_KEY_NEXT_VIEW);assert(g_eeGeneral.view==VIEW_CHAN_MONITOR&&dirty==1);
#if defined(TEST_PREVIOUS_VIEW)
 menuMainView(EVT_KEY_PREVIOUS_VIEW);assert(g_eeGeneral.view==0&&dirty==2);
#endif
 g_eeGeneral.view=VIEW_INPUTS;menuMainView(EVT_KEY_NEXT_PAGE);assert(g_eeGeneral.view==(VIEW_INPUTS|ALTERNATE_VIEW));
#endif
 menuMainView(EVT_KEY_MODEL_MENU);assert(pushed==menuModelSelect);
 menuMainView(EVT_KEY_GENERAL_MENU);assert(pushed==menuRadioTools);
 menuMainView(EVT_KEY_TELEMETRY);assert(chained==menuViewTelemetry);
 menuMainView(EVT_KEY_LAST_MENU);assert(pushed==menuModelSelect);
 menuMainView(EVT_KEY_STATISTICS);assert(chained==menuStatisticsView);
 menuMainView(EVT_KEY_CONTEXT_MENU);
#if defined(TYVOR_HOME)
 assert(popup==3); // Channel Monitor + optional notes + standard entries.
#else
 assert(popup==2);
#endif
}
'''
        code = '#include <initializer_list>\n' + code
        with tempfile.TemporaryDirectory(prefix='tyvor-home-nav-') as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(code)
            for tyvor in (False,True):
                for previous in (False,True):
                    flags=(['-DTYVOR_HOME'] if tyvor else [])+(['-DTEST_PREVIOUS_VIEW'] if previous else [])
                    subprocess.run(['g++','-std=c++17','-fsanitize=undefined',
                                    '-fno-sanitize-recover=all',*flags,str(p/'test.cpp'),'-o',str(p/'test')],check=True)
                    subprocess.run([str(p/'test')],check=True)

    def test_monitor_banks_are_independent_bounded_and_return_to_caller(self):
        text=(ROOT/'radio/src/gui/128x64/view_channels.cpp').read_text()
        dispatcher=text[text.index('void menuChannelsView(event_t event)'):]
        code=r'''
#include <cassert>
#include <cstdint>
using event_t=uint16_t;
constexpr int EVT_ENTRY=1,EVT_KEY_NEXT_PAGE=2,EVT_KEY_PREVIOUS_PAGE=3,EVT_KEY_NEXT_VIEW=4,KEY_EXIT=5;
#define EVT_KEY_BREAK(k) (100+(k))
#if defined(TEST_PREVIOUS_VIEW)
#define EVT_KEY_PREVIOUS_VIEW 6
#endif
constexpr unsigned ALTERNATE_VIEW=16;
struct {uint8_t view;}g_eeGeneral;
static uint8_t channelsPage=0;
static unsigned popped=0,drawn=0;
void popMenu(){++popped;}
void menuChannelsViewCommon(event_t){++drawn;}
'''+dispatcher+r'''
int main(){
#if defined(TYVOR_CHANNEL_MONITOR)
 for(unsigned saved=0;saved<256;++saved){
  g_eeGeneral.view=saved;channelsPage=3;menuChannelsView(EVT_ENTRY);assert(channelsPage==0);
  for(unsigned n=0;n<40;++n){
   menuChannelsView(EVT_KEY_NEXT_PAGE);assert(channelsPage==(n+1)%4);
   assert(g_eeGeneral.view==saved);
  }
  menuChannelsView(EVT_KEY_PREVIOUS_PAGE);assert(channelsPage==3);
  menuChannelsView(EVT_KEY_NEXT_VIEW);assert(channelsPage==0);
#if defined(TEST_PREVIOUS_VIEW)
  menuChannelsView(EVT_KEY_PREVIOUS_VIEW);assert(channelsPage==3);
#endif
  assert(g_eeGeneral.view==saved);
  menuChannelsView(EVT_KEY_BREAK(KEY_EXIT));assert(popped==saved+1);
 }
#else
 g_eeGeneral.view=3;menuChannelsView(EVT_KEY_NEXT_PAGE);assert(g_eeGeneral.view==19);
 menuChannelsView(EVT_KEY_PREVIOUS_PAGE);assert(g_eeGeneral.view==3);
 menuChannelsView(EVT_KEY_NEXT_VIEW);assert(g_eeGeneral.view==3);
 menuChannelsView(EVT_KEY_BREAK(KEY_EXIT));assert(popped==1);
#endif
 assert(drawn>0);
}
'''
        with tempfile.TemporaryDirectory(prefix='tyvor-monitor-nav-') as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(code)
            for target in (False,True):
                for previous in (False,True):
                    flags=(['-DTYVOR_CHANNEL_MONITOR'] if target else [])+(['-DTEST_PREVIOUS_VIEW'] if previous else [])
                    subprocess.run(['g++','-std=c++17','-fsanitize=undefined','-fno-sanitize-recover=all',*flags,str(p/'test.cpp'),'-o',str(p/'test')],check=True)
                    subprocess.run([str(p/'test')],check=True)

    def test_home_context_monitor_opens_without_resetting_timers(self):
        text=(ROOT/'radio/src/gui/128x64/view_main.cpp').read_text()
        callback=text[text.index('void onMainViewMenu('):text.index('void drawSmallSwitch(')]
        code=r'''
#include <cassert>
#include <cstdint>
using event_t=uint16_t;
using Handler=void(*)(event_t);
#define TIMERS 3
const char *STR_CHANNELS_MONITOR="channels",*STR_RESET_TIMER1="t1",*STR_RESET_TIMER2="t2",*STR_RESET_TIMER3="t3",*STR_VIEW_NOTES="notes",*STR_RESET_SUBMENU="reset",*STR_RESET_SESSION="session",*STR_RESET_TELEMETRY="telemetry",*STR_STATISTICS="stats",*STR_ABOUT_US="about";
Handler pushed=nullptr,chained=nullptr;unsigned resets=0;
void menuChannelsView(event_t){}void menuStatisticsView(event_t){}void menuAboutView(event_t){}
void pushMenu(Handler h){pushed=h;}void chainMenu(Handler h){chained=h;}
void timerReset(int){++resets;}void telemetryReset(){++resets;}void flightReset(){++resets;}
void pushModelNotes(){}
#define POPUP_MENU_START(...) ((void)0)
'''+callback+r'''
int main(){
 onMainViewMenu(STR_CHANNELS_MONITOR);
#if defined(TYVOR_HOME)
 assert(pushed==menuChannelsView);
#else
 assert(!pushed);
#endif
 assert(!resets&&!chained);
 onMainViewMenu(STR_RESET_TIMER1);assert(resets==1);
 onMainViewMenu(nullptr);assert(resets==1);
}
'''
        with tempfile.TemporaryDirectory(prefix='tyvor-home-context-') as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(code)
            for target in (False,True):
                flags=['-DTYVOR_HOME'] if target else []
                subprocess.run(['g++','-std=c++17','-fsanitize=undefined','-fno-sanitize-recover=all',*flags,str(p/'test.cpp'),'-o',str(p/'test')],check=True)
                subprocess.run([str(p/'test')],check=True)
