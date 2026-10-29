Danh sách stage và lệnh Git — chỉ để người dùng thực hiện

Đã kiểm tra branch SAOLALINKV1, base HEAD de56c3127e0f288041759675149cb712f3f2a196, index trống trước backup. Tag tyvor-v1-stable-20261029 chưa tồn tại tại thời điểm kiểm tra. Remote tên origin có sẵn; không lưu URL/credential trong gói.

Có 18 file tracked sửa đổi (17 source firmware/simulator +1 test), 40 source/test/tool mới; cộng giấy phép, tài liệu cần thiết, 39 framebuffer fixtures và gói release. Danh sách máy đọc chính xác: STAGE_FILES.txt. Chỉ có metadata backup/attribute binary mới được thêm trong lượt này; không sửa chức năng/source firmware.

Không stage toàn repo bằng `git add .` hoặc `git add -A`: working tree còn nhiều tài liệu thử nghiệm, log và ảnh cũ ngoài scope bản stable. Không stage build-*/, .venv, cache, log, ELF/object/map, runtime simulator, model/radio settings, SD cá nhân, font TTF/OTF, file cấu hình Studio hoặc credential. Hai BIN trong releases/ là artifact stable được yêu cầu lưu, không phải build tạm. Không stage các submodule chỉ có khác CRLF; không thay gitlink và không reset/clean chúng.

Tại repo, người dùng tự chạy sau khi đọc danh sách:

```sh
git status --short
git branch --show-current
python3 releases/tyvor-v1-stable-20261029/verify_backup.py
git add --pathspec-from-file=releases/tyvor-v1-stable-20261029/STAGE_FILES.txt
git diff --cached --name-only
git diff --cached --stat
git diff --cached --check
```

Trên PowerShell dùng `py` hoặc Python venv thay python3. Kiểm tra index chỉ chứa danh sách đã duyệt; nếu còn file đã stage từ công việc khác, chưa commit cho đến khi tự phân tách đúng scope. Không dùng reset/clean trên WIP để làm working tree sạch.

Sau khi tự duyệt staged diff, người dùng có thể thực hiện:

```sh
git commit -m "release: archive TYVOR V1 stable 2026-10-29"
git show --stat --oneline HEAD
git tag -a tyvor-v1-stable-20261029 -m "TYVOR V1 STABLE — 2026-10-29"
git push origin SAOLALINKV1
git push origin refs/tags/tyvor-v1-stable-20261029
```

Không dùng --force hoặc push tất cả tag. Những lệnh trên chưa được Codex thực hiện. Commit/tag sẽ trỏ source WIP đã lưu; manifest BIN gốc vẫn ghi base commit lúc build. README giải thích sự khác biệt này.

Danh sách đầy đủ theo nhóm:

**Source firmware/simulator đã sửa**

- `radio/src/edgetx.cpp`
- `radio/src/gui/128x64/CMakeLists.txt`
- `radio/src/gui/128x64/model_setup.cpp`
- `radio/src/gui/128x64/radio_setup.cpp`
- `radio/src/gui/128x64/splash.cpp`
- `radio/src/gui/128x64/startup_shutdown.cpp`
- `radio/src/gui/128x64/view_about.cpp`
- `radio/src/gui/128x64/view_channels.cpp`
- `radio/src/gui/128x64/view_main.cpp`
- `radio/src/gui/common/stdlcd/menu_radio.cpp`
- `radio/src/gui/common/stdlcd/splash.cpp`
- `radio/src/main.cpp`
- `radio/src/storage/sdcard_common.cpp`
- `radio/src/targets/simu/display.cpp`
- `radio/src/targets/simu/sdl_simu.cpp`
- `radio/src/targets/simu/simulib.cpp`
- `radio/src/telemetry/telemetry_sensors.h`

**Source/assets mới**

- `radio/src/bitmaps/128x64/tyvor_owl.png`
- `radio/src/bitmaps/128x64/tyvor_wordmark.png`
- `radio/src/gui/128x64/tyvor_fc_arm.cpp`
- `radio/src/gui/128x64/tyvor_fc_arm.h`
- `radio/src/gui/128x64/tyvor_flight_data.h`
- `radio/src/gui/128x64/tyvor_flight_timer.cpp`
- `radio/src/gui/128x64/tyvor_flight_timer.h`
- `radio/src/gui/128x64/tyvor_home.h`
- `radio/src/gui/128x64/tyvor_menu.h`
- `radio/src/gui/128x64/tyvor_power.h`
- `radio/src/gui/128x64/tyvor_timer.h`
- `radio/src/targets/simu/desktop_controls.h`

**Test/runner/generator**

- `radio/util/tests/fixtures/tyvor_betaflight_arm.cpp`
- `radio/util/tests/fixtures/tyvor_crsf_pipeline.cpp`
- `radio/util/tests/fixtures/tyvor_home_altitude.cpp`
- `radio/util/tests/fixtures/tyvor_home_rf_ui.cpp`
- `radio/util/tests/fixtures/tyvor_time_arm_pipeline.cpp`
- `radio/util/tests/fixtures/tyvor_universal_timer.cpp`
- `radio/util/tests/run_tyvor_betaflight_arm.py`
- `radio/util/tests/run_tyvor_crsf_pipeline.py`
- `radio/util/tests/run_tyvor_home_altitude.py`
- `radio/util/tests/run_tyvor_home_rf_ui.py`
- `radio/util/tests/run_tyvor_time_arm_pipeline.py`
- `radio/util/tests/run_tyvor_universal_timer.py`
- `radio/util/tests/test_saolalink_storage.py`
- `radio/util/tests/test_tyvor_betaflight_arm.py`
- `radio/util/tests/test_tyvor_crsf_pipeline.py`
- `radio/util/tests/test_tyvor_desktop.py`
- `radio/util/tests/test_tyvor_flight_data.py`
- `radio/util/tests/test_tyvor_flight_timer.py`
- `radio/util/tests/test_tyvor_home.py`
- `radio/util/tests/test_tyvor_home_altitude.py`
- `radio/util/tests/test_tyvor_home_navigation.py`
- `radio/util/tests/test_tyvor_home_rf_ui.py`
- `radio/util/tests/test_tyvor_menus.py`
- `radio/util/tests/test_tyvor_monochrome.py`
- `radio/util/tests/test_tyvor_power.py`
- `radio/util/tests/test_tyvor_time_arm.py`
- `tools/render-tyvor-timer.py`
- `tools/render-tyvor-wordmark.py`
- `tools/run-tyvor-simulator.sh`

**Tài liệu/giấy phép và fixture attributes**

- `docs/branding/tyvor-mono-polish/.gitattributes`
- `docs/branding/tyvor-simulator-upgrade/FONT_LICENSE.md`
- `docs/branding/tyvor-simulator-upgrade/font-source.json`
- `docs/building/tyvor-simulator-led-guard.patch`
- `docs/building/tyvor-simulator.md`

**Framebuffer fixtures 1 KiB**

- `docs/branding/tyvor-mono-polish/after/about.bin`
- `docs/branding/tyvor-mono-polish/after/channel-monitor.bin`
- `docs/branding/tyvor-mono-polish/after/hardware-bottom.bin`
- `docs/branding/tyvor-mono-polish/after/hardware-focus.bin`
- `docs/branding/tyvor-mono-polish/after/hardware-screen.bin`
- `docs/branding/tyvor-mono-polish/after/hardware-top.bin`
- `docs/branding/tyvor-mono-polish/after/home-return.bin`
- `docs/branding/tyvor-mono-polish/after/home.bin`
- `docs/branding/tyvor-mono-polish/after/model-popup.bin`
- `docs/branding/tyvor-mono-polish/after/models.bin`
- `docs/branding/tyvor-mono-polish/after/popup.bin`
- `docs/branding/tyvor-mono-polish/after/settings-editing.bin`
- `docs/branding/tyvor-mono-polish/after/settings-selection.bin`
- `docs/branding/tyvor-mono-polish/after/settings.bin`
- `docs/branding/tyvor-mono-polish/after/telemetry.bin`
- `docs/branding/tyvor-mono-polish/after/tools.bin`
- `docs/branding/tyvor-mono-polish/after/warning.bin`
- `docs/branding/tyvor-mono-polish/before/about.bin`
- `docs/branding/tyvor-mono-polish/before/channel-monitor.bin`
- `docs/branding/tyvor-mono-polish/before/home-return.bin`
- `docs/branding/tyvor-mono-polish/before/home.bin`
- `docs/branding/tyvor-mono-polish/before/model-popup.bin`
- `docs/branding/tyvor-mono-polish/before/models.bin`
- `docs/branding/tyvor-mono-polish/before/popup.bin`
- `docs/branding/tyvor-mono-polish/before/settings-editing.bin`
- `docs/branding/tyvor-mono-polish/before/settings-selection.bin`
- `docs/branding/tyvor-mono-polish/before/settings.bin`
- `docs/branding/tyvor-mono-polish/before/telemetry.bin`
- `docs/branding/tyvor-mono-polish/before/tools.bin`
- `docs/branding/tyvor-mono-polish/before/warning.bin`
- `docs/branding/tyvor-mono-polish/inverted/about-inverted.bin`
- `docs/branding/tyvor-mono-polish/inverted/editing-inverted.bin`
- `docs/branding/tyvor-mono-polish/inverted/home-inverted.bin`
- `docs/branding/tyvor-mono-polish/inverted/model-popup-inverted.bin`
- `docs/branding/tyvor-mono-polish/inverted/models-inverted.bin`
- `docs/branding/tyvor-mono-polish/inverted/popup-inverted.bin`
- `docs/branding/tyvor-mono-polish/inverted/selection-inverted.bin`
- `docs/branding/tyvor-mono-polish/inverted/settings-inverted.bin`
- `docs/branding/tyvor-mono-polish/inverted/warning-inverted.bin`

**Release backup**

- `releases/tyvor-v1-stable-20261029/.gitattributes`
- `releases/tyvor-v1-stable-20261029/BUILD.md`
- `releases/tyvor-v1-stable-20261029/BUILD_OPTIONS.json`
- `releases/tyvor-v1-stable-20261029/README.md`
- `releases/tyvor-v1-stable-20261029/RELEASE_FILES.sha256`
- `releases/tyvor-v1-stable-20261029/SHA256SUMS`
- `releases/tyvor-v1-stable-20261029/SOURCE_STATE.json`
- `releases/tyvor-v1-stable-20261029/STAGE_FILES.txt`
- `releases/tyvor-v1-stable-20261029/STAGING.md`
- `releases/tyvor-v1-stable-20261029/TEST_RESULTS.json`
- `releases/tyvor-v1-stable-20261029/application.bin`
- `releases/tyvor-v1-stable-20261029/application.manifest.json`
- `releases/tyvor-v1-stable-20261029/firmware.bin`
- `releases/tyvor-v1-stable-20261029/firmware.manifest.json`
- `releases/tyvor-v1-stable-20261029/home-simulator.png`
- `releases/tyvor-v1-stable-20261029/verify_backup.py`

