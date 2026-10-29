"""Exercise the real SDL pixel converter, including unaffected target profiles."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SIMU = ROOT / 'radio/src/targets/simu'
FRAMES = ROOT / 'docs/branding/tyvor-mono-polish'


def function(text, signature):
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'


@unittest.skipUnless(shutil.which('g++') and shutil.which('pkg-config'),
                     'requires host g++ and SDL2 development headers')
class TyvorMonochromeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        flags = subprocess.run(['pkg-config', '--cflags', 'sdl2'],
                               capture_output=True, text=True)
        if flags.returncode:
            raise unittest.SkipTest('requires SDL2 development headers')
        cls.tmp = tempfile.TemporaryDirectory(prefix='tyvor-mono-')
        cls.addClassCleanup(cls.tmp.cleanup)
        directory = Path(cls.tmp.name)
        display = (SIMU / 'display.cpp').read_text()
        frontend = (SIMU / 'sdl_simu.cpp').read_text()
        descriptor = frontend[frontend.index('  const ScreenDesc desc = {'):]
        descriptor = descriptor[:descriptor.index('  };') + len('  };')]
        source = r'''
#include <SDL.h>
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>
constexpr int LCD_W=128,LCD_H=64,LCD_DEPTH=1;
uint8_t simuLcdBuf[1024];
struct { bool invertLCD; } g_eeGeneral;
using ImU32=uint32_t;
#define IM_COL32(r,g,b,a) (uint32_t(r)|(uint32_t(g)<<8)|(uint32_t(b)<<16)|(uint32_t(a)<<24))
#define IM_COL32_BLACK_TRANS IM_COL32(0,0,0,0)
bool backlight=false;
bool isBacklightEnabled() { return backlight; }
struct ScreenDesc { int width,height; bool is_dot_matrix; };
'''
        source += function(display, 'static void _set_pixel(')
        source += function(display, 'static void _blit_simu_screen_1bit(')
        source += function(frontend, 'ImU32 get_bg_color()')
        source += 'ScreenDesc descriptor() {\n' + descriptor + '\nreturn desc;\n}\n'
        source += r'''
void check_frame(bool invert) {
  g_eeGeneral.invertLCD=invert;
  std::array<uint8_t,1024> before;
  std::copy_n(simuLcdBuf,1024,before.begin());
  std::array<uint8_t,128*64*4+32> texture;
  texture.fill(0xDA);
  _blit_simu_screen_1bit(texture.data()+16,SDL_PIXELFORMAT_RGBA8888,128,64,128*4);
  assert(std::equal(before.begin(),before.end(),simuLcdBuf));
  for(int i=0;i<16;i++) {
    assert(texture[i]==0xDA);
    assert(texture[texture.size()-1-i]==0xDA);
  }
  for(int y=0;y<64;y++) for(int x=0;x<128;x++) {
    const bool set=before[(y/8)*128+x] & (1<<(y%8));
    const auto* rgba=texture.data()+16+(y*128+x)*4;
#if defined(RADIO_SAOLALINKV1) && defined(SAOLALINK_DEVEBOX)
    const uint8_t expected=(set!=invert)?255:0;
    assert(rgba[0]==255);
    assert(rgba[1]==expected && rgba[2]==expected && rgba[3]==expected);
#else
    assert(rgba[0]==(set?255:0));
    assert(rgba[1]==0 && rgba[2]==0 && rgba[3]==0);
#endif
  }
}
int main(int argc,char** argv) {
  const std::string mode=argv[1];
  if(mode=="palette") {
    // Every possible page byte, in both hardware inversion states.
    for(int byte=0;byte<256;byte++) {
      std::fill_n(simuLcdBuf,1024,byte);
      check_frame(false);check_frame(true);
    }
    // Non-uniform columns/pages expose row order, stride and dropped pixels.
    for(int i=0;i<1024;i++) simuLcdBuf[i]=(i*73+(i/128)*19)&255;
    check_frame(false);check_frame(true);
  } else if(mode=="frames") {
    assert(argc>2);
    for(int i=2;i<argc;i++) {
      std::ifstream in(argv[i],std::ios::binary);
      const std::vector<char> data((std::istreambuf_iterator<char>(in)),{});
      assert(data.size()==1024);
      std::copy(data.begin(),data.end(),simuLcdBuf);
      check_frame(false);check_frame(true);
    }
  } else if(mode=="presentation") {
    for(bool enabled:{false,true}) {
      backlight=enabled;
#if defined(RADIO_SAOLALINKV1) && defined(SAOLALINK_DEVEBOX)
      assert(get_bg_color()==IM_COL32(0,0,0,255));
      assert(!descriptor().is_dot_matrix);
#else
      assert(get_bg_color()==(enabled?IM_COL32(47,123,227,255):IM_COL32(200,200,200,255)));
      assert(descriptor().is_dot_matrix);
#endif
      assert(descriptor().width==128 && descriptor().height==64);
    }
  } else return 2;
}
'''
        cpp = directory / 'check.cpp'
        cpp.write_text(source)
        cls.binaries = {}
        for name, defines in {
            'devebox': ['RADIO_SAOLALINKV1', 'SAOLALINK_DEVEBOX'],
            'saolalink_without_devebox': ['RADIO_SAOLALINKV1'],
            'unrelated_with_devebox_flag': ['SAOLALINK_DEVEBOX'],
            'generic_mono': [],
        }.items():
            binary = directory / name
            subprocess.run(['g++', '-std=c++17', '-O2', *flags.stdout.split(),
                            *['-D' + define for define in defines],
                            str(cpp), '-o', str(binary)], check=True,
                           capture_output=True, text=True)
            cls.binaries[name] = binary

    def run_profiles(self, mode, *args):
        for name, binary in self.binaries.items():
            with self.subTest(profile=name):
                subprocess.run([str(binary), mode, *map(str, args)], check=True,
                               capture_output=True, text=True)

    def test_pixel_polarity_inversion_and_framebuffer_immutability(self):
        self.run_profiles('palette')

    def test_real_ui_frames_preserve_every_pixel_in_both_polarities(self):
        frames = sorted(FRAMES.glob('*/*.bin'))
        if not frames:
            self.skipTest('real GUI framebuffer captures not available')
        self.run_profiles('frames', *frames)

    def test_oled_presentation_is_target_scoped_and_ignores_lcd_backlight_tint(self):
        self.run_profiles('presentation')


if __name__ == '__main__':
    unittest.main()
