#include "edgetx.h"
#include "tyvor_flight_timer.h"
#if defined(TYVOR_FLIGHT_TIMER_UI)
#include "telemetry/crossfire.h"
#include "hal/switch_driver.h"

static constexpr const char* configKey="TYVOR.FlightTimer.v1";
static TyvorFlightTimerConfig config, editConfig;
static TyvorFlightClock clockState;
static bool loaded=false;
static TyvorArmState timerSignal=TyvorArmState::Unknown;
static const char* statusText="";

static uint16_t moduleSignature()
{
  return uint16_t(g_model.moduleData[0].type) | (uint16_t(g_model.moduleData[1].type)<<8);
}

static bool timerSwitchAvailable(int source)
{
  const int s=source<0 ? -source : source;
  return !s || (s>=SWSRC_FIRST_SWITCH && s<=SWSRC_LAST_SWITCH && isSwitchAvailableInMixes(source));
}

static bool autoSensorAvailable(int source)
{
  if (!source) return true;
  if (source<1 || source>MAX_TELEMETRY_SENSORS) return false;
  const auto& s=g_model.telemetrySensors[source-1];
  if (!s.isAvailable() || s.type!=TELEM_TYPE_CUSTOM || s.unit!=UNIT_RAW || s.prec ||
      s.autoOffset || s.filter || s.onlyPositive || s.custom.ratio || s.custom.offset) return false;
  unsigned active=0;
  for (unsigned i=0;i<2;++i) {
    if (g_model.moduleData[i].type==MODULE_TYPE_NONE) continue;
    ++active;
    if (isModuleCrossfire(i)) {
      // Known CRSF GPS/battery/link/mode values cannot be selected as FC ARM.
      switch(s.id) {
        case GPS_ID: case GPS_TIME_ID: case CF_VARIO_ID: case BATTERY_ID:
        case BARO_ALT_ID: case AIRSPEED_ID: case CF_RPM_ID: case TEMP_ID:
        case CELLS_ID: case VOLT_ARRAY_ID: case LINK_ID: case LINK_RX_ID:
        case LINK_TX_ID: case ATTITUDE_ID: case FLIGHT_MODE_ID: return false;
      }
    }
  }
  return active==1;
}

TyvorArmState tyvorFlightTimerArm()
{
  if (!loaded || !config.verified || !config.sensor ||
      config.modules!=moduleSignature() || !autoSensorAvailable(config.sensor) ||
      !TELEMETRY_STREAMING()) return TyvorArmState::Unknown;
  const unsigned index=config.sensor-1;
  const auto& s=g_model.telemetrySensors[index]; const auto& item=telemetryItems[index];
  if (s.id!=config.sensorId || s.instance!=config.instance || s.subId!=config.subId ||
      !tyvorFlightSensorFresh(true,item.timeout,TELEMETRY_SENSOR_TIMEOUT_START,12) ||
      !tyvorFlightReceivedRecently(get_tmr10ms(),item.tyvorReceivedAt,192)) return TyvorArmState::Unknown;
  for (unsigned i=0;i<MAX_TELEMETRY_SENSORS;++i) {
    if (i==index) continue;
    const auto& other=g_model.telemetrySensors[i];
    if (other.isAvailable() && other.type==TELEM_TYPE_CUSTOM && other.id==s.id &&
        other.instance==s.instance && other.subId==s.subId) return TyvorArmState::Unknown;
  }
  return item.value==0 ? TyvorArmState::Disarmed :
         item.value==1 ? TyvorArmState::Armed : TyvorArmState::Unknown;
}

void tyvorFlightTimerModelLoaded(bool valid)
{
  config={};
  if (valid) {
    const auto* data=g_model.getUserData(configKey);
    if (data && data->type==UD_STRING) {
      TyvorFlightTimerConfig parsed;
      if (tyvorDecodeFlightConfig(data->value.c_str(),parsed) &&
          parsed.sensor<=MAX_TELEMETRY_SENSORS && timerSwitchAvailable(parsed.switchSource)) config=parsed;
    }
  }
  clockState.clear(get_tmr10ms()); timerSignal=TyvorArmState::Unknown; loaded=true;
}

void tyvorFlightTimerPoll()
{
  if (!loaded) return;
  timerSignal=TyvorArmState::Unknown;
  if (config.mode==TyvorFlightTimerMode::Auto) timerSignal=tyvorFlightTimerArm();
  else if (config.switchSource && timerSwitchAvailable(config.switchSource))
    timerSignal=getSwitch(config.switchSource) ? TyvorArmState::Armed : TyvorArmState::Disarmed;
  clockState.update(get_tmr10ms(),timerSignal);
}

void tyvorFlightTimerReset() { clockState.clear(get_tmr10ms(),true); }
bool tyvorFlightTimerHasTime() { return clockState.hasTime; }
uint32_t tyvorFlightTimerSeconds() { return clockState.seconds(); }
const TyvorFlightTimerConfig& tyvorFlightTimerSettings() { return config; }
const char* tyvorFlightTimerTag()
{
  if (config.mode==TyvorFlightTimerMode::Auto)
    return timerSignal==TyvorArmState::Unknown ? "AUTO?" : "AUTO";
  return timerSignal==TyvorArmState::Unknown || !clockState.ready ? "SW?" : "SW";
}

static void confirmSource(const char* result)
{
  if (result==STR_OK) editConfig.verified=true;
}
static void confirmReset(const char* result)
{
  if (result==STR_OK) {tyvorFlightTimerReset();statusText="Reset: OFF then ON";}
}

void menuTyvorFlightTimer(event_t event)
{
  if (event==EVT_ENTRY) {editConfig=config;statusText="";}
  enum {MODE,SWITCH,FC_SENSOR,VERIFIED,RESET,SAVE,COUNT};
  const bool automatic=editConfig.mode==TyvorFlightTimerMode::Auto;
  SUBMENU("FLIGHT TIMER",COUNT,{0,uint8_t(automatic?HIDDEN_ROW:0),
          uint8_t(automatic?0:HIDDEN_ROW),uint8_t(automatic?0:HIDDEN_ROW),0,0});
  const int sub=menuVerticalPosition;
  unsigned visible=0;
  for (unsigned i=0;i<COUNT;++i) {
    if ((i==SWITCH && automatic) || ((i==FC_SENSOR || i==VERIFIED) && !automatic)) continue;
    const coord_t y=9+visible++*8;
    const LcdFlags attr=sub==int(i) ? (s_editMode>0 ? INVERS|BLINK : INVERS) : 0;
    switch(i) {
      case MODE: {
        lcdDrawText(2,y,"Mode"); lcdDrawText(78,y,automatic?"AUTO":"SWITCH",attr);
        if (attr && s_editMode>0) editConfig.mode=TyvorFlightTimerMode(checkIncDec(event,int(editConfig.mode),0,1,0));
        break;
      }
      case SWITCH:
        lcdDrawText(2,y,"Timer switch");drawSwitch(86,y,editConfig.switchSource,attr);
        if (attr && s_editMode>0) editConfig.switchSource=checkIncDec(event,editConfig.switchSource,-SWSRC_LAST_SWITCH,SWSRC_LAST_SWITCH,INCDEC_SWITCH,timerSwitchAvailable);
        break;
      case FC_SENSOR: {
        lcdDrawText(2,y,"FC ARM 0/1");
        if (editConfig.sensor) lcdDrawSizedText(83,y,g_model.telemetrySensors[editConfig.sensor-1].label,TELEM_LABEL_LEN,attr);
        else lcdDrawText(83,y,"---",attr);
        if (attr && s_editMode>0) {
          const int selected=checkIncDec(event,editConfig.sensor,0,MAX_TELEMETRY_SENSORS,0,autoSensorAvailable);
          if (selected!=editConfig.sensor) {
            editConfig.sensor=selected;editConfig.verified=false;editConfig.modules=moduleSignature();
            if (selected) {const auto& s=g_model.telemetrySensors[selected-1];editConfig.sensorId=s.id;editConfig.instance=s.instance;editConfig.subId=s.subId;}
          }
        }
        break;
      }
      case VERIFIED:
        lcdDrawText(2,y,"FC verified");lcdDrawText(83,y,editConfig.verified?"YES":"NO",attr);
        if (attr && event==EVT_KEY_BREAK(KEY_ENTER)) {
          s_editMode=0;
          if (editConfig.verified) editConfig.verified=false;
          else if (editConfig.sensor && autoSensorAvailable(editConfig.sensor)) POPUP_CONFIRMATION("FC ARM 0=OFF 1=ON",confirmSource);
          else statusText="Select FC sensor";
        }
        break;
      case RESET:
        lcdDrawText(2,y,"Reset flight time",attr);
        if (attr && event==EVT_KEY_BREAK(KEY_ENTER)) {s_editMode=0;POPUP_CONFIRMATION("Reset flight time?",confirmReset);}
        break;
      case SAVE:
        lcdDrawText(2,y,"Save",attr);
        if (attr && event==EVT_KEY_BREAK(KEY_ENTER)) {
          s_editMode=0;char text[64];tyvorEncodeFlightConfig(text,editConfig);
          if (g_model.setUserData(configKey,text)) {config=editConfig;tyvorFlightTimerReset();statusText="Saved: OFF then ON";}
          else statusText="Save failed: data full";
        }
        break;
    }
  }
  if (*statusText) lcdDrawText(2,57,statusText,SMLSIZE);
  else if (!clockState.ready && timerSignal==TyvorArmState::Armed) lcdDrawText(2,57,"Switch/status OFF first",SMLSIZE);
}
#endif
