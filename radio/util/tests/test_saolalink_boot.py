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
                            '-I', str(root), str(harness), '-o', str(root / 'boot')],
                           check=True, capture_output=True, text=True)
            subprocess.run([str(root / 'boot')], check=True)
