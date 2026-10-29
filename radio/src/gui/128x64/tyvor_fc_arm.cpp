#include "edgetx.h"
#include "tyvor_fc_arm.h"
#if defined(TYVOR_FC_ARM_UI)
#include "tyvor_flight_timer.h"
#include "telemetry/crossfire.h"

static constexpr const char* fcConfigKey = "TYVOR.FcArm.v1";
static TyvorFcArmConfig fcConfig, fcDraft;
static bool invalidConfig = false;
static const char* fcStatus = "";

static uint16_t fcModules()
{
  return uint16_t(g_model.moduleData[0].type) | (uint16_t(g_model.moduleData[1].type) << 8);
}

static bool fcSensorAvailable(int source)
{
  if (!source) return true;
  if (source < 1 || source > MAX_TELEMETRY_SENSORS) return false;
  unsigned active = 0;
  for (unsigned i = 0; i < 2; ++i) {
    if (g_model.moduleData[i].type == MODULE_TYPE_NONE) continue;
    if (!isModuleCrossfire(i)) return false;
    ++active;
  }
  const auto& s = g_model.telemetrySensors[source - 1];
  return active == 1 && s.isAvailable() && s.type == TELEM_TYPE_CUSTOM &&
         s.id == FLIGHT_MODE_ID && !s.instance && !s.subId && s.unit == UNIT_TEXT &&
         !s.prec && !s.autoOffset && !s.filter && !s.onlyPositive &&
         !s.custom.ratio && !s.custom.offset;
}

void tyvorFcArmModelLoaded(bool valid)
{
  fcConfig = {}; invalidConfig = !valid;
  if (!valid) return;
  const auto* data = g_model.getUserData(fcConfigKey);
  if (!data) return;
  TyvorFcArmConfig parsed;
  if (data->type != UD_STRING || !tyvorDecodeFcArmConfig(data->value.c_str(), parsed) ||
      parsed.sensor > MAX_TELEMETRY_SENSORS) invalidConfig = true;
  else fcConfig = parsed;
}

const TyvorFcArmConfig& tyvorFcArmSettings() { return fcConfig; }

struct FcArmReading { TyvorArmState arm; const char* reason; };

static FcArmReading readFcArm()
{
  using S = TyvorArmState;
  if (invalidConfig) return {S::Unknown, "FC config invalid"};
  if (fcConfig.profile == TyvorFcArmProfile::Unconfigured) {
    auto arm = tyvorFlightTimerArm();
    return {arm, arm == S::Unknown ? "Set FC profile + Save" : "Verified RAW 0/1"};
  }
  if (fcConfig.profile != TyvorFcArmProfile::Betaflight455) return {S::Unknown, "Unsupported FC"};
  if (!fcConfig.sensor) return {S::Unknown, "Select FM + Save"};
  if (!fcConfig.verified) return {S::Unknown, "Verify FC + Save"};
  if (fcConfig.modules != fcModules()) return {S::Unknown, "RF source changed"};
  if (!fcSensorAvailable(fcConfig.sensor)) return {S::Unknown, "FM ID/unit/source"};
  if (!TELEMETRY_STREAMING()) return {S::Unknown, "No telemetry"};
  const unsigned index = fcConfig.sensor - 1;
  const auto& item = telemetryItems[index];
  if (!tyvorFlightSensorFresh(true, item.timeout, TELEMETRY_SENSOR_TIMEOUT_START, 12) ||
      !tyvorFlightReceivedRecently(get_tmr10ms(), item.tyvorReceivedAt, 192)) return {S::Unknown, "FM stale"};
  for (unsigned i = 0; i < MAX_TELEMETRY_SENSORS; ++i) {
    if (i == index) continue;
    const auto& sensor = g_model.telemetrySensors[i];
    if (sensor.isAvailable() && sensor.type == TELEM_TYPE_CUSTOM && sensor.id == FLIGHT_MODE_ID &&
        !sensor.instance && !sensor.subId) return {S::Unknown, "Duplicate FM"};
  }
  auto arm = tyvorDecodeFcArm(fcConfig.profile, item.text, sizeof(item.text));
  return {arm, arm == S::Armed ? "FC ARMED" : arm == S::Disarmed ? "FC DISARMED" : "Unsupported FM"};
}

TyvorArmState tyvorHomeFcArm() { return readFcArm().arm; }
const char* tyvorFcArmStatusText() { return readFcArm().reason; }

static void confirmFc(const char* result)
{
  if (result == STR_OK) { fcDraft.modules = fcModules(); fcDraft.verified = true; }
}

void menuTyvorFcArm(event_t event)
{
  if (event == EVT_ENTRY) { fcDraft = fcConfig; fcStatus = ""; }
  enum { PROFILE, SENSOR, VERIFIED, SAVE, COUNT };
  const bool betaflight = fcDraft.profile == TyvorFcArmProfile::Betaflight455;
  SUBMENU("FC ARM TELEMETRY", COUNT, {0, uint8_t(betaflight ? 0 : HIDDEN_ROW),
          uint8_t(betaflight ? 0 : HIDDEN_ROW), 0});
  const int sub = menuVerticalPosition;
  unsigned visible = 0;
  for (unsigned i = 0; i < COUNT; ++i) {
    if (!betaflight && (i == SENSOR || i == VERIFIED)) continue;
    const coord_t y = 9 + visible++ * 8;
    const LcdFlags attr = sub == int(i) ? (s_editMode > 0 ? INVERS | BLINK : INVERS) : 0;
    switch (i) {
      case PROFILE:
        lcdDrawText(2, y, "FC profile");
        lcdDrawText(78, y, betaflight ? "BF4.5.5" : "RAW/--", attr);
        if (attr && s_editMode > 0) {
          auto selected = TyvorFcArmProfile(checkIncDec(event, int(fcDraft.profile), 0, 1, 0));
          if (selected != fcDraft.profile) { fcDraft.profile = selected; fcDraft.verified = false; }
        }
        break;
      case SENSOR:
        lcdDrawText(2, y, "FM sensor");
        if (fcDraft.sensor) lcdDrawSizedText(83, y, g_model.telemetrySensors[fcDraft.sensor - 1].label, TELEM_LABEL_LEN, attr);
        else lcdDrawText(83, y, "---", attr);
        if (attr && s_editMode > 0) {
          const int selected = checkIncDec(event, fcDraft.sensor, 0, MAX_TELEMETRY_SENSORS, 0, fcSensorAvailable);
          if (selected != fcDraft.sensor) {
            fcDraft.sensor = selected; fcDraft.modules = fcModules(); fcDraft.verified = false;
          }
        }
        break;
      case VERIFIED:
        lcdDrawText(2, y, "FC verified"); lcdDrawText(83, y, fcDraft.verified ? "YES" : "NO", attr);
        if (attr && event == EVT_KEY_BREAK(KEY_ENTER)) {
          s_editMode = 0;
          if (fcDraft.verified) fcDraft.verified = false;
          else if (fcDraft.sensor && fcSensorAvailable(fcDraft.sensor)) POPUP_CONFIRMATION("Betaflight 4.5.5?", confirmFc);
          else fcStatus = "Select FM sensor";
        }
        break;
      case SAVE:
        lcdDrawText(2, y, "Save", attr);
        if (attr && event == EVT_KEY_BREAK(KEY_ENTER)) {
          s_editMode = 0; char text[40]; tyvorEncodeFcArmConfig(text, fcDraft);
          if (g_model.setUserData(fcConfigKey, text)) {
            fcConfig = fcDraft; invalidConfig = false; fcStatus = "Saved: model only";
          }
          else fcStatus = "Save failed: data full";
        }
        break;
    }
  }
  if (fcDraft.sensor && fcDraft.sensor <= MAX_TELEMETRY_SENSORS) {
    const auto& sensor = g_model.telemetrySensors[fcDraft.sensor - 1];
    char identity[32];
    snprintf(identity, sizeof(identity), "ID%04X I%u S%u U%u P%u", unsigned(sensor.id),
             unsigned(sensor.instance), unsigned(sensor.subId), unsigned(sensor.unit), unsigned(sensor.prec));
    lcdDrawText(2, 41, identity, TINSIZE);
  }
  lcdDrawText(2, 49, *fcStatus ? fcStatus : betaflight ? "4.5.5 only; FS unknown" : "Existing RAW 0/1 only", SMLSIZE);
  lcdDrawText(2, 57, tyvorFcArmStatusText(), SMLSIZE);
}
#endif
