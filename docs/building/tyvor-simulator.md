# TYVOR — build và mở GUI Simulator thực tế

Nguồn hiện tại: nhánh `SAOLALINKV1`, gồm branding TYVOR đang có trong working
tree. Dùng target native SDL `simu`, DevEBox 8 MHz / SAOLALINK_V1 / 128×64 mono.
Đây là simulator của firmware, không phải PNG/mockup Phase 2 hay render harness.
Không cần ARM toolchain hoặc Qt cho đường SDL này; Companion/Qt là đường khác.

## Kết quả kiểm tra 2026-10-26

| Hạng mục | Trạng thái |
| --- | --- |
| WSL2, Ubuntu-22.04, x86_64 | PASS |
| WSLg, DISPLAY=:0, X11 socket ngoài sandbox | PASS: kết nối được |
| Git, GCC/G++, Ninja, Python 3.10 | PASS |
| CMake dùng để build | PASS: 3.31.10 trong build venv; bản hệ thống 3.22.1 giữ nguyên |
| SDL2 development files và pkg-config | PASS: SDL2 2.0.20, gói hệ thống do người dùng cài sau khi cho phép |
| LLVM/libclang và builtin headers | PASS: libclang 14 và builtin headers được kiểm tra |
| Python build packages | PASS: dependency của pyproject.toml, clang binding 14.0.6, cài trong build venv |
| Python venv | PASS: build-tyvor-simu/venv, Python 3.10.12; bootstrap cục bộ bằng virtualenv |
| Công cụ Windows native | NOT VERIFIED: chạy powershell.exe từ phiên này báo Exec format error |
| Native build/link | PASS sau guard LED một dòng đã được người dùng duyệt riêng |
| Target thực tế | PASS: macro SIMU, RADIO_SAOLALINKV1, SAOLALINK_DEVEBOX, LCD_W=128, LCD_H=64, LCD_DEPTH=1 |
| GUI / phím / ảnh chụp | PASS: cửa sổ EdgeTx Simu thật, 960×640, LCD logic 128×64 mono bên trong |
| Host regression | PASS: 12/12 test_saolalink*.py sau guard LED |
| Phần cứng thật | NOT VERIFIED: không build/flash/test firmware trên tay điều khiển |

Người dùng đã cho phép cài dependency. `sudo -n` yêu cầu mật khẩu nên các gói
Ubuntu được người dùng cài trong Terminal; không nhận mật khẩu qua chat.
Dependency Python/CMake được chuẩn bị cục bộ. Qt và ARM toolchain không được cài.

## Ngoại lệ source duy nhất đã được duyệt

Build đầu tiên dừng ở `main.cpp:580` vì đoạn heartbeat LED DevEBox dùng GPIOA
trực tiếp khi compile native. Sau khi kiểm tra patch, người dùng cho phép thêm
`&& !defined(SIMU)` đúng guard ở đầu `perMain()` trong `radio/src/main.cpp`.
Patch: [tyvor-simulator-led-guard.patch](tyvor-simulator-led-guard.patch).

Diff chỉ đổi một dòng. Đối chiếu tiền xử lý xác nhận nhánh LED DevEBox thật,
target thật khác và simulator khác giống bản trước; chỉ DevEBox SIMU bỏ GPIO.
Không đổi UI, RF, mixer, failsafe, calibration, pins, board hoặc bootloader.
Đây là kiểm tra source/PC, không phải xác minh phần cứng thật.

## Ảnh chụp và điều hướng đã kiểm tra

Tất cả ảnh sau lấy trực tiếp từ cửa sổ X11 của SDL simulator, không từ mockup:

- [HOME](../../build-tyvor-simu/screenshots/home.png)
- [Context menu](../../build-tyvor-simu/screenshots/main-menu.png)
- [Models](../../build-tyvor-simu/screenshots/models.png)
- [Radio Settings](../../build-tyvor-simu/screenshots/settings.png)
- [Channel Monitor](../../build-tyvor-simu/screenshots/channel-monitor.png)
- [Telemetry — chưa cấu hình screen](../../build-tyvor-simu/screenshots/telemetry.png)
- [About TYVOR](../../build-tyvor-simu/screenshots/about-tyvor.png)

Lần đầu có Storage Warning/Storage preparation do settings riêng còn trống;
đã đi qua bằng phím theo UI thật. Sau đó thoát First Calibration bằng Esc,
không tự tạo calibration giả. MODEL01 do lifecycle simulator tạo mặc định.
Đã dùng M, S, T, PageUp/PageDown, Up/Down, Enter/giữ Enter và Esc để mở/đóng
các màn trên; cuối cùng trả về HOME và giữ cửa sổ mở.

## Các bước khắc phục — chỉ chạy khi người dùng cho phép

Mở Ubuntu-22.04. Các lệnh sau **cài phần mềm**, chưa được tự thực hiện:

```sh
sudo apt-get update
sudo apt-get install libsdl2-dev pkg-config clang-14 libclang-14-dev python3-venv
```

Không cần chạy script setup toàn bộ EdgeTX (script đó còn cài ARM/Qt và các
thành phần không cần cho simulator SDL). Sau khi các gói trên đã được cho phép:

```sh
cd /mnt/d/Projects/SAOLALINK/edgetx
python3 -m venv build-tyvor-simu/venv
build-tyvor-simu/venv/bin/python -m pip install 'cmake>=3.25,<4' 'clang==14.0.6' -e .
bash tools/run-tyvor-simulator.sh --check
bash tools/run-tyvor-simulator.sh
```

Python binding [clang 14.0.6](https://pypi.org/project/clang/14.0.6/) được chọn
cùng dòng libclang 14. Các gói Python và CMake được cài trong build venv,
không ghi vào Python hệ thống. CMake mới ở venv tránh thay bản CMake hệ thống;
[preset schema 6 cần CMake 3.25 trở lên](https://cmake.org/cmake/help/v3.25/manual/cmake-presets.7.html).
Dependency C++ (ImGui, GoogleTest, miniz, yaml-cpp...) được CMake tải theo source
repo vào `build-tyvor-simu/deps`; cần Internet ở lần build đầu.

## Mở nhanh những lần sau

Từ Ubuntu:

```sh
bash /mnt/d/Projects/SAOLALINK/edgetx/tools/run-tyvor-simulator.sh
```

Từ PowerShell Windows:

```powershell
wsl.exe -d Ubuntu-22.04 -- bash /mnt/d/Projects/SAOLALINK/edgetx/tools/run-tyvor-simulator.sh
```

Script configure ở lần đầu, xác minh cache đúng source/profile ở những lần sau,
rồi build tăng dần và mở cửa sổ. Ninja tự xử lý thay đổi CMake/source. Kiểm tra
warm build đã trả về `ninja: no work to do`. `--check` chỉ kiểm tra, `--build`
chỉ build. Nếu đúng simulator đang chạy, script dùng lại cửa sổ thay vì mở
thêm; muốn build thay đổi mới thì đóng cửa sổ cũ trước. Có khóa tránh hai workflow
cùng build/chạy trên một thư mục.
Không tự chạy apt/pip, không đổi firmware source, không flash. Output nằm trong
`build-tyvor-simu/` đã được gitignore; SD/settings riêng trong `runtime/`.
Simulator tự tạo radio/model defaults qua lifecycle thật, không ghi dữ liệu mẫu
cố định và không đọc settings/SD của tay điều khiển. Telemetry chưa cấu hình có
thể báo chưa có screens/data; đó là trạng thái thật của simulator.

## Điều khiển bàn phím

Click cửa sổ simulator trước khi thao tác. Mapping từ `targets/simu/sdl_simu.cpp`
và `gui/navigation/navigation.h`:

| Phím PC | Chức năng |
| --- | --- |
| Enter / giữ Enter | Enter / context menu (Reset, Statistics, About...) |
| Esc | RTN/Exit |
| M | Models |
| S | Radio settings tabs; tab đầu có thể là Tools |
| T | Telemetry |
| PageUp / PageDown | HOME views; trong nhóm menu/telemetry theo navigation hiện có |
| Up / Down | Rotary encoder navigation |

Channel Monitor nằm trong chu kỳ HOME views; Enter chuyển channel/mixer monitor.
Các stick/switch/pot controls của SDL simulator cũng được hiển thị để thao tác.
Cửa sổ 960×640 gồm control panels; LCD firmware bên trong vẫn là **128×64 mono**.

Xác minh mới khi chạy thật: SDL gọi `simuStart()` với mặc định `tests=true`
trong `simulib.h:50`. Chỉ nhánh `tests=false` mới tự thêm NO_SPLASH,
NO_CALIBRATION, NO_CHECKS. Điều này sửa mô tả mặc định chưa chính xác trong
các audit trước khi build; profile mới thực tế có thể hỏi First Calibration.
Không sửa startup/calibration để ép splash; About đã được chụp với branding TYVOR.
Sound safety, dữ liệu radio/model và hành vi UI chạy theo source hiện có.

## Giới hạn kiểm chứng

Launcher đã qua kiểm tra cú pháp, preflight và warm build. Native simulator đã
link và chạy GUI thật; các màn/phím nêu trên được kiểm tra. Chưa xác minh mọi
editor, file action, warning hoặc dữ liệu telemetry từ receiver thật. Không flash
hoặc thử phần cứng, không tạo screenshot giả. Chỉ main.cpp có guard LED được
duyệt; không sửa RF, mixer, failsafe, calibration, drivers, board/pins, bootloader
hoặc UI. Build output, settings và screenshots nằm trong thư mục build gitignored.
