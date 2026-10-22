"""Execute startup/shutdown and storage orchestration with a file-backed host backend.

The existing YAML codec is not replaced in firmware; only its read/write boundary
is mocked here so settings lifetime, USB gating and write ordering are exercised.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[2] / 'src'


def function(source, signature):
    start = source.index(signature)
    opening = source.index('{', start)
    depth = 1
    pos = opening + 1
    while depth:
        depth += (source[pos] == '{') - (source[pos] == '}')
        pos += 1
    return source[start:pos] + '\n'


@unittest.skipUnless(shutil.which('g++'), 'requires host g++')
class DeveboxStorageTests(unittest.TestCase):
    def compile_run(self, source):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'storage.cpp').write_text(source)
            result = subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra',
                                     '-Wno-unused-parameter', str(root / 'storage.cpp'),
                                     '-o', str(root / 'storage')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(root / 'storage')], cwd=root, check=True)

    def test_actual_startup_calibration_save_shutdown_and_cold_reload(self):
        app = (SRC / 'edgetx.cpp').read_text()
        common = (SRC / 'storage/sdcard_common.cpp').read_text()
        storage = (SRC / 'storage/storage_common.cpp').read_text()
        main = (SRC / 'main.cpp').read_text()
        model = (SRC / 'model_init.cpp').read_text()
        defaults = function(app, 'void generalDefault()').split(
            '#if defined(SAOLALINK_DEVEBOX)', 1)[1].split('#endif', 1)[0]
        body = r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <fstream>
#include <filesystem>
#include <stdexcept>
#include <string>
#include <vector>
#define SAOLALINK_DEVEBOX
#define GUI
#define LCD_W 128
#define OPENTX_START_NO_SPLASH 1
#define OPENTX_START_NO_CALIBRATION 2
#define OPENTX_START_NO_CHECKS 4
#define UNEXPECTED_SHUTDOWN() emergency
#define TRACE(...) ((void)0)
#define ALERT(...) (++warnings)
#define RAISE_ALERT(...) (++warnings)
#define BACKLIGHT_ENABLE() ((void)0)
#define AUDIO_BYE() ((void)0)
#define AUDIO_HELLO() ((void)0)
#define PLAY_MODEL_NAME() ((void)0)
#define IS_PLAYING(x) false
#define LED_ERROR_END() ((void)0)
#define WDG_ENABLE(x) ((void)0)
#define EE_GENERAL 1
#define EE_MODEL 2
#define ADC_INPUT_MAIN 0
#define BACKLIGHT_FORCED_ON 1
#define TELEM_TYPE_CALCULATED 1
#define MAX_TELEMETRY_SENSORS 0
#define MAX_POTS 2
#define POTS_WARN_AUTO 1
#define SAVE_POT_POSITION(i) ((void)0)
#define SP_VCP 0
#define UART_MODE_CLI 7
#define INTERNAL_MODULE 0
#define EXTERNAL_MODULE 1
#define MODULE_TYPE_NONE 0
#define MODULE_TYPE_CROSSFIRE 5
#define CROSSFIRE_INDEX_TO_STORE(i) ((i)+1)
#define RADIO_PATH "RADIO"
#define MODELS_PATH "MODELS"
#define MODELIDX_STRLEN 8
#define YAML_EXT ".yml"
#define STR_MODEL "Model"
#define STR_NO_SDCARD "No SD card"
#define TIME_TO_WRITE() (storageDirtyMsk && uint32_t(get_tmr10ms()-storageDirtyTime10ms)>=500)
using tmr10ms_t=uint32_t;
enum {USB_UNSELECTED_MODE, USB_SERIAL_MODE, USB_JOYSTICK_MODE, USB_MASS_STORAGE_MODE};
enum {e_backlight_mode_off};
struct CalibData {int16_t mid,spanNeg,spanPos;};
struct TelemetrySensor {int type;bool persistent;int persistentValue;};
struct Radio {
 CalibData calib[6]; uint16_t chkSum; uint8_t stickMode,currModel,USBMode;
 uint8_t serialMode,pwrOffSpeed,internalModule,internalModuleBaudrate;
 uint32_t globalTimer; bool invertLCD,modelCustomScriptsDisabled,dontPlayHello;
 int backlightMode; char uiLanguage[3],ttsLanguage[3];
 int getBrightness() const {return 50;}
} g_eeGeneral;
struct Model {
 struct {char name[16];} header;
 struct {uint8_t type;} moduleData[2];
 TelemetrySensor telemetrySensors[1];
 uint8_t potsWarnMode,potsWarnEnabled;
 int gain;
} g_model;
struct {int value;} telemetryItems[1];
uint8_t storageDirtyMsk=0,startOptions=0;
uint32_t storageDirtyTime10ms=0,ms=0,sessionTimer=0;
bool emergency=false,mounted=false,cardPresent=true,writeFailure=false,suspendI2CTasks=false;
unsigned defaultsCalls=0,modelDefaultsCalls=0,calibPrompts=0,warnings=0;
int selectedUsb=USB_SERIAL_MODE;
int currentBacklightBright,requiredBacklightBright,currentLanguagePackIdx,currentLanguagePack;
int languagePacks[]={0};
std::vector<std::string> events;
uint32_t time_get_ms() {return ms;}
uint32_t get_tmr10ms() {return ms/10;}
bool usbPlugged() {return true;} // DevEBox VBUS fallback
int getSelectedUsbMode() {return selectedUsb;}
unsigned adcGetMaxInputs(unsigned) {return 4;}
void serialSetMode(unsigned,int mode) {g_eeGeneral.serialMode=mode;}
void storageDirty(uint8_t);
void storageCheck(bool);
uint16_t evalChkSum();
void setModelDefaults(uint8_t id=0);
void setModuleType(unsigned idx,uint8_t type) {g_model.moduleData[idx].type=type;}
void applyDefaultTemplate() {++modelDefaultsCalls;g_model.gain=100;storageDirty(EE_MODEL);}
void generalDefaultUILanguage() {strcpy(g_eeGeneral.uiLanguage,"en");}
void generalDefault() {
 ++defaultsCalls;memset(&g_eeGeneral,0,sizeof(g_eeGeneral));g_eeGeneral.stickMode=1;
 generalDefaultUILanguage();strcpy(g_eeGeneral.ttsLanguage,"en");
 for(auto& c:g_eeGeneral.calib) c={1023,1000,1000};
''' + defaults + r'''
 g_eeGeneral.chkSum=0xFFFF;
}
char* strAppend(char* dst,const char* text) {strcpy(dst,text);return dst+strlen(dst);}
char* strAppendUnsigned(char* dst,unsigned n,unsigned width) {sprintf(dst,"%0*u",width,n);return dst;}
void sdCheckAndCreateDirectory(const char* name) {std::filesystem::create_directory(name);}
void sdInit() {events.emplace_back("mount");mounted=cardPresent;}
bool sdMounted() {return mounted;}
void sdDone() {events.emplace_back("unmount");assert(storageDirtyMsk==0);mounted=false;}
void loadModelHeaders() {}
int getLanguageId(const char*) {return 0;}
void preModelLoad() {}
void postModelLoad(bool) {}
void saveTimers() {storageDirty(EE_MODEL);}
void disableUncalibratedXPots() {}
void getModelNumberStr(unsigned idx,char* out) {sprintf(out,"model%u",idx);}
std::string modelPath(const char* name) {return std::string("MODELS/")+name;}
const char* loadRadioSettingsYaml(bool) {
 std::ifstream in("RADIO/radio.bin",std::ios::binary);
 if(!mounted||!in.read((char*)&g_eeGeneral,sizeof(g_eeGeneral))) return "read failure";
 return nullptr;
}
const char* loadRadioSettings() {return loadRadioSettingsYaml(true);}
const char* writeGeneralSettings() {
 if(writeFailure||!mounted) return "write failure";
 events.emplace_back("write radio");
 std::ofstream out("RADIO/radio.bin",std::ios::binary);
 out.write((char*)&g_eeGeneral,sizeof(g_eeGeneral));return out?nullptr:"write failure";
}
const char* writeModel() {
 if(writeFailure||!mounted) return "write failure";
 char name[16];getModelNumberStr(g_eeGeneral.currModel,name);strcat(name,YAML_EXT);
 events.emplace_back("write model");std::ofstream out(modelPath(name),std::ios::binary);
 out.write((char*)&g_model,sizeof(g_model));return out?nullptr:"write failure";
}
const char* readModel(const char* name,uint8_t* data,uint32_t length,const char*) {
 std::ifstream in(modelPath(name),std::ios::binary);
 return in.read((char*)data,length)?nullptr:"read failure";
}
const char* loadModel(const char* name,bool alarms=true,const char* path=nullptr);
const char* loadModel(uint8_t idx,bool alarms=true);
void watchdogSuspend(unsigned) {}
void pulsesStop() {}
void pulsesStart() {}
void logsClose() {events.emplace_back("close logs");}
void logsInit() {events.emplace_back("init logs");}
void sleep_ms(unsigned delay) {ms+=delay;}
void lcdRefreshWait() {}
void lcdClear() {}
void lcdRefresh() {}
void lcdSetInvert(bool) {}
void lcdSetContrast() {}
void menuMainView() {}
void menuModelSelect() {}
void menuFirstCalib() {}
void (*menuHandlers[2])();
void startSplash() {}
void waitSplash() {}
void cancelSplash() {}
void chainMenu(void (*)()) {++calibPrompts;}
void checkAlarm() {}
void checkAll(bool) {}
void resetBacklightTimeout() {}
void pwrOn() {}
void runFatalErrorScreen(const char*) {throw std::runtime_error("missing SD");}
void luaInitMainState() {}
void initSerialPorts() {}
void referenceSystemAudioFiles() {}
struct {void start() {}} audioQueue;
'''
        parts = [function(app, 'uint16_t evalChkSum()'),
                 function(storage, 'void storageDirty(uint8_t msk)'),
                 function(SRC.joinpath('hal/adc_driver.cpp').read_text(), 'void adcCalibStore()'),
                 function(model, 'void setVendorSpecificModelDefaults(uint8_t id)'),
                 function(model, 'void setModelDefaults(uint8_t id)'),
                 function(common, 'static void forceSave()'),
                 function(common, 'static void storageFormat()'),
                 function(common, 'static void storageEraseAll()'),
                 function(common, 'void storageCheck(bool immediately)'),
                 function(common, 'const char* loadModel(const char* filename'),
                 function(SRC.joinpath('storage/sdcard_yaml.cpp').read_text(), 'const char * loadModel(uint8_t idx'),
                 function(common, 'void storageReadAll()'),
                 function(SRC.joinpath('storage/sdcard_yaml.cpp').read_text(), 'bool storageReadRadioSettings(bool checks)'),
                 function(main, 'void checkStorageUpdate()'),
                 function(main, 'static bool storageUpdateAllowed()'),
                 function(storage, 'void storageFlushCurrentModel()'),
                 function(app, 'void edgeTxInit()'), function(app, 'void edgeTxClose(uint8_t shutdown)')]
        body += '\n'.join(parts) + r'''
void coldBoot() {
 memset(&g_eeGeneral,0,sizeof(g_eeGeneral));memset(&g_model,0,sizeof(g_model));
 storageDirtyMsk=0;startOptions=0;mounted=false;suspendI2CTasks=false;events.clear();
 edgeTxInit();
}
int main() {
 // Blank card follows the normal first-run/default/calibration path once.
 coldBoot();
 assert(defaultsCalls==1&&modelDefaultsCalls==1&&calibPrompts==1);
 assert(g_eeGeneral.USBMode==USB_SERIAL_MODE&&g_eeGeneral.serialMode==UART_MODE_CLI);
 assert(g_eeGeneral.internalModuleBaudrate==CROSSFIRE_INDEX_TO_STORE(1));
 assert(g_model.moduleData[0].type==MODULE_TYPE_CROSSFIRE);
 assert(!(startOptions&OPENTX_START_NO_CALIBRATION));
 // Calibration and stick-mode change, while the CDC port is active.
 for(unsigned i=0;i<6;++i) g_eeGeneral.calib[i]={int16_t(1900+i),int16_t(1700+i),int16_t(1800+i)};
 g_eeGeneral.stickMode=3;adcCalibStore();
 assert(storageDirtyMsk&EE_GENERAL);
 assert(storageUpdateAllowed());
 ms+=4990;checkStorageUpdate();assert(storageDirtyMsk&EE_GENERAL);
 ms+=10;checkStorageUpdate();assert(storageDirtyMsk==0);
 const Radio calibrated=g_eeGeneral;
 coldBoot();
 assert(defaultsCalls==1&&modelDefaultsCalls==1&&calibPrompts==1);
 assert(g_eeGeneral.stickMode==3&&g_eeGeneral.chkSum==evalChkSum());
 assert(!memcmp(calibrated.calib,g_eeGeneral.calib,sizeof(calibrated.calib)));
 // Saved user choices must not be replaced by development defaults on restart.
 g_eeGeneral.currModel=3;g_eeGeneral.pwrOffSpeed=2;g_eeGeneral.USBMode=USB_JOYSTICK_MODE;
 g_eeGeneral.internalModuleBaudrate=4;g_model.gain=73;
 g_model.moduleData[0].type=MODULE_TYPE_NONE;
 storageDirty(EE_GENERAL|EE_MODEL);sessionTimer=12;
 edgeTxClose(1);assert(!mounted&&sessionTimer==0&&storageDirtyMsk==0);
 assert(events.back()=="unmount");
 coldBoot();
 assert(defaultsCalls==1&&modelDefaultsCalls==1&&calibPrompts==1);
 assert(g_eeGeneral.currModel==3&&g_eeGeneral.stickMode==3&&g_model.gain==73);
 assert(g_eeGeneral.globalTimer==12&&g_eeGeneral.pwrOffSpeed==2);
 assert(g_eeGeneral.USBMode==USB_JOYSTICK_MODE&&g_eeGeneral.internalModuleBaudrate==4);
 assert(g_model.moduleData[0].type==MODULE_TYPE_NONE);
 // A failed write retains dirty state and retries instead of claiming success.
 writeFailure=true;g_eeGeneral.stickMode=0;storageDirty(EE_GENERAL);
 storageCheck(true);assert(storageDirtyMsk&EE_GENERAL);
 writeFailure=false;storageCheck(true);assert(storageDirtyMsk==0);
 coldBoot();assert(g_eeGeneral.stickMode==0);
 // A missing card follows the existing fatal-screen path, never resets SD settings.
 cardPresent=false;const auto calls=defaultsCalls;
 try {coldBoot();assert(false);} catch(const std::runtime_error&) {}
 assert(defaultsCalls==calls);
}
'''
        self.compile_run(body)

    def test_usb_serial_allows_saves_but_mass_storage_blocks_them(self):
        main = (SRC / 'main.cpp').read_text()
        gate = function(main, 'static bool storageUpdateAllowed()')
        # Compile the real helper for both the DevEBox and unchanged generic case.
        for devebox in (False, True):
            with self.subTest(devebox=devebox):
                self.compile_run(('#define SAOLALINK_DEVEBOX\n' if devebox else '') + r'''
#include <cassert>
enum {USB_UNSELECTED_MODE,USB_SERIAL_MODE,USB_JOYSTICK_MODE,USB_MASS_STORAGE_MODE};
bool plugged=true;
int mode;
bool usbPlugged() {return plugged;}
int getSelectedUsbMode() {return mode;}
''' + gate + '\nint main() {\n' + r'''
 mode=USB_UNSELECTED_MODE;assert(storageUpdateAllowed());
 mode=USB_SERIAL_MODE;
''' + f' assert(storageUpdateAllowed()=={str(devebox).lower()});\n'
                + ' mode=USB_JOYSTICK_MODE;\n'
                + f' assert(storageUpdateAllowed()=={str(devebox).lower()});\n' + r'''
 mode=USB_MASS_STORAGE_MODE;assert(!storageUpdateAllowed());
 plugged=false;mode=USB_UNSELECTED_MODE;assert(storageUpdateAllowed());
}
''')
        per_main = function(main, 'void perMain()')
        # Cover both write polling and card remount paths that used VBUS before.
        self.assertEqual(per_main.count('if (storageUpdateAllowed())'), 2)
