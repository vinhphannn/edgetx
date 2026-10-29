Tái tạo source/build TYVOR V1 stable

Cần base commit và toàn bộ file trong STAGE_FILES.txt. Phải commit các file WIP trước khi dùng tag làm mốc source. Không dùng riêng commit de56c312 để tái tạo tính năng mới.

1. Khởi tạo dependency tại gitlink đã ghi: `git submodule update --init --recursive`. Chỉ thực hiện trong clone/checkout dùng để build; không dùng lệnh reset/clean trên WIP hiện tại. Các submodule báo dirty tại thời điểm backup chỉ khác CRLF/LF; commit vẫn khớp và không có thay đổi source cần stage. SOURCE_STATE.json ghi cả các submodule FreeRTOS lồng nhau.
2. Đường chính: SaolaLink Studio, chọn source checkout, DevEBox 8 MHz, Debug, Build firmware. Setup phải nhận GNU ARM 14.2.1. ARM firmware không dùng host Clang. libclang host chỉ phục vụ generator khi cần.
3. Các dependency generator Python do Studio Setup cung cấp; simulator Linux cần compiler host, SDL2-dev/pkg-config, CMake >=3.25, Ninja, Python có Pillow và dependency dự án. Không nhúng font TTF/OTF: bitmap wordmark và timer header đã có trong source. Script font chỉ để tạo lại asset khi có font hợp lệ.

Tùy chọn CMake ARM tương đương build gốc (PowerShell; thay đường tool theo máy, không chạy flash):

```powershell
$tyvorSource = (Get-Location).Path
$tyvorBuild = Join-Path $tyvorSource 'build-tyvor-v1-stable-rebuild'
$tyvorArm = 'C:/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/14.2 rel1/bin'
$tyvorPython = 'D:/Tool/saolalink-studio/.venv/Scripts/python.exe'
cmake -S $tyvorSource -B $tyvorBuild -G Ninja `
  "-DCMAKE_TOOLCHAIN_FILE=$tyvorSource/cmake/toolchain/arm-none-eabi.cmake" `
  -DEdgeTX_SUPERBUILD=OFF -DNATIVE_BUILD=OFF -DPCB=X7 -DPCBREV=SAOLALINK_V1 `
  -DCMAKE_BUILD_TYPE=Debug -DDEFAULT_MODE=2 -DTRANSLATIONS=EN -DUSE_FW_LTO=ON `
  -DBOOTLOADER=ON -DFIRMWARE_STRIP_BOOTLOADER=OFF -DFIRMWARE_FORMAT_UF2=OFF `
  "-DPython3_EXECUTABLE=$tyvorPython" "-DARM_TOOLCHAIN_DIR=$tyvorArm" `
  -DSAOLALINK_HSE_HZ=8000000 -DSAOLALINK_DEVEBOX=ON
cmake --build $tyvorBuild --target hardware_defs --parallel 4
cmake --build $tyvorBuild --target firmware --parallel 4
```

CMake/Ninja/Git phải ở PATH; nếu không, truyền CMAKE_MAKE_PROGRAM/GIT_EXECUTABLE như cấu hình Studio. Lệnh configure thành công phải in GNU 14.2.1 và CMake Generic/arm-none-eabi. Dừng nếu compiler/profile không đúng. Đây là công thức ghi từ build đã PASS; không tuyên bố đã chạy lại trên checkout sạch sau commit.

Simulator từ WSLg:

```sh
bash tools/run-tyvor-simulator.sh --check
bash tools/run-tyvor-simulator.sh --build
```

Script không tự cài dependency. Sau khi đã có venv theo docs/building/tyvor-simulator.md, chạy đầy đủ regression với native build mới. Ví dụ dưới dùng thư mục simulator mặc định do script trên tạo:

```sh
export TYVOR_NATIVE_BUILD="$PWD/build-tyvor-simu"
export TYVOR_ALT_TEST_OUTPUT="$PWD/build-tyvor-stable-tests/altitude"
export TYVOR_HOME_RF_TEST_OUTPUT="$PWD/build-tyvor-stable-tests/home-rf"
export TYVOR_BF455_TEST_OUTPUT="$PWD/build-tyvor-stable-tests/bf455"
export TYVOR_CRSF_TEST_OUTPUT="$PWD/build-tyvor-stable-tests/crsf"
export TYVOR_TIME_ARM_TEST_OUTPUT="$PWD/build-tyvor-stable-tests/legacytimer"
export TYVOR_UNIVERSAL_TIMER_TEST_OUTPUT="$PWD/build-tyvor-stable-tests/universal-timer"
build-tyvor-simu/venv/bin/python -B -m unittest discover -s radio/util/tests -p 'test_tyvor*.py' -v
build-tyvor-simu/venv/bin/python -B -m unittest discover -s radio/util/tests -p 'test_saolalink*.py' -v
```

Kỳ vọng 41 +12 =53 test, không skip khi đủ dependency và framebuffer fixtures. 39 file *.bin tại docs/branding/tyvor-mono-polish/{before,after,inverted} là fixture màn hình 1024 byte/frame cho test_tyvor_monochrome.py, không phải firmware hoặc output build tạm. Giữ chúng trong commit để regression trên clone mới không bị skip.

Điều hướng stable hiện tại: HOME giữ ENTER → Channel Monitor, không nằm trong vòng PAGE HOME cũ. Tài liệu simulator lịch sử có thể mô tả vòng HOME cũ; README stable này là mốc áp dụng.

Build từ tag mới có thể đổi stamp commit/version, timestamp và debug path, nên hash build mới có thể khác BIN stable dù chức năng tương đương. Chưa thực hiện kiểm chứng bit-for-bit trên clone sạch. Không thay đổi/ghi đè BIN backup để cập nhật manifest của một build khác.
