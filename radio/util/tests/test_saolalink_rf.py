"""Exercise the actual CRSF reassembly/CRC path and DevEBox diagnostic states."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[2] / 'src'
TARGET = SRC / 'targets/taranis/saolalink_v1'


@unittest.skipUnless(shutil.which('g++'), 'requires host g++')
class DeveboxRFTests(unittest.TestCase):
    def compile_run(self, source):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cpp = root / 'rf.cpp'
            cpp.write_text(source)
            result = subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', str(cpp), '-o', str(root / 'rf')],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(root / 'rf')], check=True)

    def test_status_sessions_staleness_and_wrap(self):
        self.compile_run(f'#include "{TARGET / "rf_monitor.h"}"\n#include <cassert>\n' + r'''
int main() {
  DeveboxRFMonitor d;
  assert(d.link(false, 0)==d.OFF);
  d.beginSession(400000);
  assert(d.baud==400000 && d.link(true, 0)==d.UART_DOWN);
  d.uartReady=true;
  d.txQueued=1000;
  assert(d.link(true, 10000)==d.WAIT_RX); // transmitting is not a reply
  d.rxBytes+=12;
  assert(d.link(true, 10000)==d.BAD_RX); // bytes alone are not valid CRSF
  d.validFrame(10000);
  assert(d.goodFrames==1 && d.link(true, 12000)==d.OK);
  assert(d.link(true, 12001)==d.STALE);
  assert(d.link(false, 12001)==d.OFF);
  d.beginSession(400000); d.uartReady=true;
  assert(d.goodFrames==1 && d.link(true, 12002)==d.WAIT_RX); // old frames not reused
  d.validFrame(0xFFFFFF00U);
  assert(d.link(true, 0x100U)==d.OK);
  assert(d.link(true, 0x1000U)==d.STALE);
}
''')

    def test_real_parser_fragmentation_bad_crc_noise_and_external_isolation(self):
        driver = (SRC / 'pulses/crossfire.cpp').read_text()
        crc_check = driver.split('static bool _checkFrameCRC', 1)[1].split('static void crossfireSendPulses', 1)[0]
        parser = driver.split('static bool _lenIsSane', 1)[1].split('static const etx_serial_init crsfSerialParams', 1)[0]
        self.compile_run(f'#include "{TARGET / "rf_monitor.h"}"\n' + r'''
#include <cassert>
#include <cstring>
#define SAOLALINK_DEVEBOX
#define INTERNAL_MODULE 0
#define UART_SYNC 0xC8
#define RADIO_ADDRESS 0xEA
#define MIN_FRAME_LEN 3
#define MIN_PAYLOAD_LEN 3
#define MAX_PAYLOAD_LEN 62
#define TELEMETRY_RX_PACKET_SIZE 128
#define TRACE(...) ((void)0)
DeveboxRFMonitor deveboxRF;
struct etx_module_state_t { unsigned module; } internal{0}, external{1};
unsigned modulePortGetModule(etx_module_state_t* st) {return st->module;}
uint32_t now, lastAlive[2];
uint32_t get_tmr10ms() {return now/10;}
uint32_t time_get_ms() {return now;}
unsigned processed[2];
void processCrossfireTelemetryFrame(unsigned m, uint8_t*, unsigned len) {
  assert(len==6); ++processed[m];
}
uint8_t crc8(const uint8_t* data, unsigned len) {
  uint8_t crc=0;
  for(unsigned i=0;i<len;++i) {
    crc^=data[i];
    for(unsigned b=0;b<8;++b) crc=uint8_t((crc<<1)^((crc&0x80)?0xD5:0));
  }
  return crc;
}
static bool _checkFrameCRC
''' + crc_check + '\nstatic bool _lenIsSane\n' + parser + r'''
int main() {
  uint8_t frame[]={UART_SYNC,4,0x7F,0x42,0x12,0};
  frame[5]=crc8(frame+2,3);
  uint8_t buf[128]={}; uint8_t count=0;
  deveboxRF.beginSession(400000); deveboxRF.uartReady=true; now=100;
  crossfireProcessFrame(&internal,frame,2,buf,&count);
  assert(count==2 && deveboxRF.goodFrames==0 && deveboxRF.rxBytes==2);
  crossfireProcessFrame(&internal,frame+2,4,buf,&count);
  assert(count==0 && deveboxRF.goodFrames==1 && processed[0]==1);
  assert(deveboxRF.lastGoodMs==100 && deveboxRF.rxBytes==6);
  // Corrupt a complete packet then append a valid one. Parser must resynchronize.
  uint8_t pair[12]; memcpy(pair,frame,6); pair[5]^=1; memcpy(pair+6,frame,6);
  now=200;
  crossfireProcessFrame(&internal,pair,sizeof(pair),buf,&count);
  assert(deveboxRF.goodFrames==2 && deveboxRF.crcErrors==1);
  assert(processed[0]==2 && deveboxRF.framingDrops>0 && count==0);
  uint32_t good=deveboxRF.goodFrames, rx=deveboxRF.rxBytes;
  crossfireProcessFrame(&external,frame,sizeof(frame),buf,&count);
  assert(processed[1]==1 && deveboxRF.goodFrames==good && deveboxRF.rxBytes==rx);
  uint8_t noise[]={1,2,3,4};
  crossfireProcessFrame(&internal,noise,sizeof(noise),buf,&count);
  assert(deveboxRF.goodFrames==good && deveboxRF.rxBytes==rx+4);
  assert(deveboxRF.link(true,2201)==DeveboxRFMonitor::STALE);
}
''')


    def test_actual_transmit_hook_counts_internal_uart_handoffs_only(self):
        driver = (SRC / 'pulses/crossfire.cpp').read_text()
        send = driver.split('static void crossfireSendPulses', 1)[1].split('static bool _lenIsSane', 1)[0]
        self.compile_run(f'#include "{TARGET / "rf_monitor.h"}"\n' + r'''
#include <cassert>
#define SAOLALINK_DEVEBOX
#define INTERNAL_MODULE 0
DeveboxRFMonitor deveboxRF;
struct etx_module_state_t {unsigned module; int tx;} internal{0,0}, external{1,0};
unsigned modulePortGetModule(etx_module_state_t* st) {return st->module;}
void crossfireSetupMixerScheduler(unsigned) {}
void setupPulsesCrossfire(unsigned, uint8_t*& buf, uint8_t, int16_t*, uint8_t) {
  *buf++=0xEE; *buf++=1; *buf++=0;
}
unsigned sent;
void sendBuffer(void*, const uint8_t* data, unsigned size) {
  assert(data[0]==0xEE && size==3); ++sent;
}
struct {void (*sendBuffer)(void*, const uint8_t*, unsigned);} serial={sendBuffer};
auto modulePortGetSerialDrv(int) {return &serial;}
void* modulePortGetCtx(int) {return nullptr;}
static void crossfireSendPulses
''' + send + r'''
int main() {
  uint8_t buf[64]; int16_t channels[16]={};
  crossfireSendPulses(&internal,buf,channels,16);
  assert(sent==1 && deveboxRF.txQueued==1 && deveboxRF.goodFrames==0);
  crossfireSendPulses(&external,buf,channels,16);
  assert(sent==2 && deveboxRF.txQueued==1);
  deveboxRF.uartReady=true;
  assert(deveboxRF.link(true,100)==DeveboxRFMonitor::WAIT_RX);
}
''')


if __name__ == '__main__':
    unittest.main()
