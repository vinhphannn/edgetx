"""Run the actual DevEBox boot-entry hook against mock GPIO and app vectors."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[2] / 'src'


@unittest.skipUnless(shutil.which('g++') and sys.platform.startswith('linux'),
                     'requires host g++ and Linux mmap')
class DeveboxBootTests(unittest.TestCase):
    def test_rtn_entry_valid_app_recovery_and_unrelated_gpio_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'hal').mkdir()
            (root / 'hal/key_driver.h').write_text('')
            (root / 'board.h').write_text(
                '#include <stdint.h>\n#define SAOLALINK_DEVEBOX\n'
                '#define APP_START_ADDRESS 0x08008000U\n')
            (root / 'stm32_cmsis.h').write_text(r'''
struct MockGPIO {uint32_t MODER, PUPDR, IDR;};
struct MockRCC {uint32_t AHB1ENR;};
static MockGPIO gpioA{}, gpioC{};
static MockRCC rcc{};
#define GPIOA (&gpioA)
#define GPIOC (&gpioC)
#define RCC (&rcc)
#define RCC_AHB1ENR_GPIOAEN (1U << 0)
#define RCC_AHB1ENR_GPIOCEN (1U << 2)
''')
            harness = root / 'boot.cpp'
            harness.write_text(
                f'#include "{SRC / "boards/generic_stm32/bl_keys.cpp"}"\n' + r'''
#include <cassert>
#include <sys/mman.h>
int main() {
  // Map the real application vector address so the production hook is
  // compiled unchanged, including its bounds and Thumb-state checks.
  auto vectors = (uint32_t*)mmap((void*)APP_START_ADDRESS, 4096,
      PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
  assert(vectors == (uint32_t*)APP_START_ADDRESS);

  RCC->AHB1ENR = 0x100;
  GPIOA->MODER = 0x12345678; GPIOA->PUPDR = 0x87654321; GPIOA->IDR = 1;
  GPIOC->MODER = 0xFFFFFFFF; GPIOC->PUPDR = 0xAAAAAAAA;
  constexpr unsigned mask = 3U << 10;
  boardBLEarlyInit();
  assert(RCC->AHB1ENR == (0x100 | RCC_AHB1ENR_GPIOCEN));
  assert(GPIOC->MODER == (0xFFFFFFFF & ~mask));
  assert(GPIOC->PUPDR == ((0xAAAAAAAA & ~mask) | (1U << 10)));
  assert(GPIOA->MODER == 0x12345678 && GPIOA->PUPDR == 0x87654321);

  GPIOC->IDR = 1U << 5; // RTN released, even with onboard PA0 held
  vectors[0] = 0x20020000; vectors[1] = APP_START_ADDRESS + 1;
  assert(!boardBLStartCondition());
  GPIOA->IDR = 0;
  assert(!boardBLStartCondition());
  GPIOC->IDR = 0; // RTN pressed LOW
  assert(boardBLStartCondition());
  GPIOC->IDR = 1U << 5;
  assert(!boardBLStartCondition());
  vectors[0] = 0x10010000; // CCM stack is valid too
  assert(!boardBLStartCondition());
  vectors[1] = 0x0807FFFF;
  assert(!boardBLStartCondition());

  // Invalid/blank images must remain recoverable without pressing RTN.
  const uint32_t invalid[][2] = {
    {0xFFFFFFFF, 0xFFFFFFFF}, {0, 0},
    {0x20000000, APP_START_ADDRESS + 1},
    {0x20020004, APP_START_ADDRESS + 1},
    {0x10000000, APP_START_ADDRESS + 1},
    {0x10010004, APP_START_ADDRESS + 1},
    {0x20010000, APP_START_ADDRESS}, // missing Thumb bit
    {0x20010000, APP_START_ADDRESS - 1},
    {0x20010000, 0x08080001},
  };
  for (const auto& v : invalid) {
    vectors[0] = v[0]; vectors[1] = v[1];
    assert(boardBLStartCondition());
  }
  assert(munmap(vectors, 4096) == 0);
}
''')
            subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I', str(root), '-I', str(SRC), str(harness), '-o', str(root / 'boot')],
                           check=True, capture_output=True, text=True)
            subprocess.run([str(root / 'boot')], check=True)

    def test_boot_init_consumes_software_handoff_before_usb_init(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            headers = {
                'stamp.h': '', 'keys.h': 'typedef int event_t;\n',
                'hal/flash_driver.h': '', 'debug.h': '#define TRACE(...)\n',
                'board.h': '''
#pragma once
#include <stdint.h>
#define SAOLALINK_DEVEBOX
#define APP_START_ADDRESS 0x08008000U
void __disable_irq(); void __enable_irq(); void __set_MSP(uint32_t);
void pwrInit(); void pwrOn(); void delaysInit(); void delay_ms(unsigned);
''',
                'stm32_cmsis.h': '''
#pragma once
struct MockGPIO {uint32_t MODER, PUPDR, IDR;};
struct MockRCC {uint32_t AHB1ENR;};
extern MockGPIO gpioC;
extern MockRCC rcc;
#define GPIOC (&gpioC)
#define RCC (&rcc)
#define RCC_AHB1ENR_GPIOCEN (1U << 2)
''',
                'hal/key_driver.h': '',
                'hal/usb_driver.h': 'void usbInit();\n',
                'hal/abnormal_reboot.h': '''
uint32_t abnormalRebootGetCmd(); void abnormalRebootResetCmd();
extern bool software;
#define WAS_RESET_BY_SOFTWARE() software
''',
                'timers_driver.h': 'void timersInit();\n',
            }
            for name, text in headers.items():
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(text)
            wrapper = root / 'boot.cpp'
            wrapper.write_text('#define main unused_boot_main\n' +
                f'#include "{SRC / "bootloader/boot.cpp"}"\n' +
                'bool forced() { return deveboxForceDFU; }\n')
            harness = root / 'test.cpp'
            harness.write_text(f'#include "{SRC / "boards/generic_stm32/bl_keys.cpp"}"\n' + r'''
#include <cassert>
#include <sys/mman.h>
MockGPIO gpioC{}; MockRCC rcc{};
bool software;
static uint32_t cmd;
static unsigned usb, timers, jumps;
struct Jump {};
void __disable_irq() {} void __enable_irq() {}
void __set_MSP(uint32_t) { ++jumps; throw Jump{}; }
void pwrInit() {} void pwrOn() {} void delaysInit() {} void delay_ms(unsigned) {}
void usbInit() { ++usb; } void timersInit() { ++timers; }
uint32_t abnormalRebootGetCmd() { return cmd; }
void abnormalRebootResetCmd() { cmd=0; }
void bootloaderInitApp(); bool forced();
static void boot(bool soft, uint32_t command, bool held, bool valid, bool expect_jump, bool expect_force) {
 software=soft; cmd=command; usb=timers=jumps=0;
 gpioC.IDR=held ? 0 : (1U<<5);
 auto v=(uint32_t*)APP_START_ADDRESS;
 v[0]=valid ? 0x20020000 : 0xFFFFFFFF; v[1]=APP_START_ADDRESS+9;
 try { bootloaderInitApp(); assert(!expect_jump); } catch(const Jump&) { assert(expect_jump); }
 assert(cmd==0);
 assert(forced()==expect_force);
 assert(usb==(expect_jump ? 0U : 1U) && timers==usb && jumps==(expect_jump ? 1U : 0U));
}
int main() {
 auto v=mmap((void*)APP_START_ADDRESS,4096,PROT_READ|PROT_WRITE,
             MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);
 assert(v==(void*)APP_START_ADDRESS);
 boot(false,0,false,true,false,false); // cold boot offers USB window
 boot(true,DEVEBOX_BOOT_APP,false,true,true,false); // timeout / successful upload
 boot(false,DEVEBOX_BOOT_APP,false,true,false,false); // stale RAM on cold boot ignored
 boot(true,DEVEBOX_BOOT_APP,false,false,false,true); // invalid app never runs
 boot(true,DEVEBOX_BOOT_APP,true,true,false,true); // physical recovery wins
 boot(true,0x55464442,false,true,false,true); // explicit DFU request consumed
 boot(true,0,false,true,false,false); // ordinary reset still offers window
 munmap(v,4096);
}
''')
            executable = root / 'test'
            subprocess.run(['g++', '-std=c++17', '-ffunction-sections', '-fdata-sections',
                '-Wl,--gc-sections', '-I', str(root), '-I', str(SRC), str(wrapper), str(harness),
                '-o', str(executable)], check=True, capture_output=True, text=True)
            subprocess.run([str(executable)], check=True)


@unittest.skipUnless(shutil.which('as') and shutil.which('ld') and shutil.which('nm'),
                     'requires host GNU binutils')
class RebootMemoryLayoutTests(unittest.TestCase):
    def test_real_linker_reserves_reboot_word_above_stack(self):
        # Use the production scripts, not mocked reset commands: startup stack
        # writes used to overwrite _reboot_cmd before main could consume it.
        linker = SRC / 'boards/generic_stm32/linker'
        layout = linker / 'stm32f40x'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for library in ('libc.a', 'libm.a', 'libgcc.a'):
                (root / library).write_bytes(b'!<arch>\n')
            assembly = root / 'stub.s'
            assembly.write_text('''
.section .text
.global Reset_Handler
Reset_Handler:
.byte 0
.section .isr_vector,"a"
.long _estack
.long Reset_Handler
.section .rebootdata,"aw"
.global _reboot_cmd
_reboot_cmd:
.long 0
''')
            subprocess.run(['as', str(assembly), '-o', str(root / 'stub.o')], check=True)
            command = ['ld', '-L', str(root), '-L', str(layout), '-L', str(linker),
                       '-T', str(linker / 'bootloader.ld'), str(root / 'stub.o'), '-o', str(root / 'stub.elf')]
            result = subprocess.run(command, cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            symbols = subprocess.run(['nm', str(root / 'stub.elf')], capture_output=True, text=True, check=True).stdout
            addresses = {parts[2]: int(parts[0], 16) for line in symbols.splitlines()
                         if len(parts := line.split()) == 3}
            self.assertEqual(addresses['_reboot_cmd'], 0x1000FFFC)
            self.assertEqual(addresses['_estack'], 0x1000FFF8)
            self.assertLessEqual(addresses['_estack'], addresses['_reboot_cmd'])
            self.assertEqual(addresses['_estack'] % 8, 0)
            # Reintroducing the former stack address must fail the link.
            (root / 'layout.ld').write_text((layout / 'layout.ld').read_text().replace(
                'STACK_ADDRESS = ORIGIN(CCM) + LENGTH(CCM) - 8;',
                'STACK_ADDRESS = ORIGIN(CCM) + LENGTH(CCM);'))
            result = subprocess.run(command, cwd=root, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Main stack overlaps persistent reboot command', result.stderr)
