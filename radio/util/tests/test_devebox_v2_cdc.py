"""Keep V2 early-CLI RX alive through USB class reset, release on serial stop."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[2] / 'src/targets/common/arm/stm32/usbd_cdc.cpp'


def function(source, signature):
    start = source.index(signature + '\n{')
    end = source.index('\n}', start) + 2
    return source[start:end]


@unittest.skipUnless(shutil.which('g++'), 'requires host C++ compiler')
class CdcLifecycleTests(unittest.TestCase):
    def test_host_reset_preserves_owner_callbacks_and_serial_stop_releases_them(self):
        text = SOURCE.read_text()
        code = r'''
#include <cassert>
#include <cstdint>
#define USBD_OK 0
static bool cdcConnected;
static void (*receiveDataCb)(uint8_t*,uint32_t);
static void (*baudRateCb)(uint32_t);
static int APP_Tx_ptr_in, APP_Tx_ptr_out;
static uint8_t UserTxBufferFS[64], UserRxBufferFS[64];
static int hUsbDevice;
void USBD_CDC_SetTxBuffer(int*, uint8_t*, int) {}
void USBD_CDC_SetRxBuffer(int*, uint8_t*) {}
void rx(uint8_t*,uint32_t) {}
void baud(uint32_t) {}
'''
        code += '\n'.join(function(text, name) for name in (
            'static int8_t VCP_Init_FS(void)',
            'static int8_t VCP_DeInit_FS(void)'))
        code += '\n#if defined(SAOLALINK_DEVEBOX_V2)\n' + function(
            text, 'static void usbSerialDeinit(void*)') + '\n#endif\n'
        code += r'''
int main() {
 receiveDataCb=rx; baudRateCb=baud;
 VCP_Init_FS(); assert(cdcConnected);
 APP_Tx_ptr_in=7; APP_Tx_ptr_out=4;
 VCP_DeInit_FS();
 assert(!cdcConnected && APP_Tx_ptr_in==0 && APP_Tx_ptr_out==0);
#if defined(SAOLALINK_DEVEBOX_V2)
 assert(receiveDataCb==rx && baudRateCb==baud);
 VCP_Init_FS(); assert(cdcConnected && receiveDataCb==rx);
 usbSerialDeinit(nullptr); assert(!receiveDataCb && !baudRateCb);
#else
 assert(!receiveDataCb && !baudRateCb);
#endif
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'test.cpp'; source.write_text(code)
            for definitions in ([], ['-DSAOLALINK_DEVEBOX_V2']):
                binary=Path(tmp)/'test'
                build=subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror',
                                      *definitions,str(source),'-o',str(binary)],
                                     capture_output=True,text=True)
                self.assertEqual(build.returncode,0,build.stderr)
                subprocess.run([str(binary)],check=True,timeout=5)
