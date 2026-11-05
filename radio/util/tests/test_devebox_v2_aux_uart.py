"""AUX enable updates only its saved port, preserving USB CLI and other modes."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[2] / 'src'


def function(source, signature):
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


@unittest.skipUnless(shutil.which('g++'), 'requires host g++')
class AuxUartTests(unittest.TestCase):
    def test_enable_is_explicit_and_preserves_other_serial_modes(self):
        cli = function((SRC / 'cli.cpp').read_text(), 'static int cliAuxUart(const char **argv)')
        setter = function((SRC / 'serial.cpp').read_text(), 'void serialSetMode(uint8_t port_nr, int mode)')
        harness = r'''
#include <cassert>
#include <cstdint>
#include <cstring>
constexpr int SP_AUX1=0,SP_VCP=2,UART_MODE_LUA=5,MAX_SERIAL_PORTS=3;
constexpr int SERIAL_CONF_MODE_MASK=0x0F,SERIAL_CONF_BITS_PER_PORT=8,EE_GENERAL=1;
struct Settings {uint32_t serialPort;};
Settings g_eeGeneral;
struct etx_serial_driver_t {};
static etx_serial_driver_t driver;
static unsigned initializations,dirty;
static bool active;
void serialInit(uint8_t port,int mode) {
 assert(port==SP_AUX1 && mode==UART_MODE_LUA);++initializations;active=true;
}
void storageDirty(int mask) {assert(mask==EE_GENERAL);++dirty;}
bool serialGetPortCtx(uint8_t port,void** ctx,const etx_serial_driver_t** drv) {
 assert(port==SP_AUX1);*ctx=active?&driver:nullptr;*drv=active?&driver:nullptr;return active;
}
int serialGetMode(uint8_t port) {return (g_eeGeneral.serialPort>>(port*8))&15;}
uint32_t serialGetBaudrate(uint8_t port) {assert(port==SP_AUX1);return active?115200:0;}
void cliSerialPrint(const char*,...) {}
''' + setter + cli + r'''
int main() {
 const char* argv[] = {"auxuart",nullptr};
 for (uint32_t saved : {0U,0xA5F68780U,0xFFFFFFFFU}) {
  g_eeGeneral.serialPort=saved;initializations=dirty=0;active=false;
  for (const char* action : {static_cast<const char*>(nullptr),"status","off","invalid"}) {
   argv[1]=action;
   assert(cliAuxUart(argv)==(!action || !strcmp(action,"status")?0:-1));
   assert(g_eeGeneral.serialPort==saved && !initializations && !dirty);
  }
  argv[1]="on";assert(cliAuxUart(argv)==0);
  assert(active && initializations==1 && dirty==1);
  assert(g_eeGeneral.serialPort==((saved&~15U)|UART_MODE_LUA));
  assert(serialGetMode(SP_VCP)==int((saved>>16)&15));
  argv[1]="status";assert(cliAuxUart(argv)==0);
  assert(initializations==1 && dirty==1);
 }
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            cpp = Path(tmp) / 'aux.cpp'
            binary = Path(tmp) / 'aux'
            cpp.write_text('#include <initializer_list>\n' + harness)
            result = subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                                     str(cpp), '-o', str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(binary)], check=True, timeout=5)
