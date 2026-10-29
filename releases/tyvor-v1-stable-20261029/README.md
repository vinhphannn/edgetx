TYVOR V1 STABLE — 2026-10-29

Bản sao lưu bộ BIN người dùng xác nhận đã nạp và chạy tốt trên tay TYVOR thật. Đây là bản sao nguyên byte của `build-tyvor-home-sats-alt/artifacts/`, không đổi tên phiên bản nhúng trong firmware và không tạo firmware mới.

Tag đề xuất: `tyvor-v1-stable-20261029`. Branch: `SAOLALINKV1`. Base commit khi build: `de56c3127e0f288041759675149cb712f3f2a196` cộng source WIP chưa commit. Chưa tạo commit hoặc tag. Danh sách source/test cần lưu nằm trong [STAGE_FILES.txt](STAGE_FILES.txt), chi tiết thao tác người dùng tự làm tại [STAGING.md](STAGING.md).

**Phần cứng và build**

STM32F407VET6, DevEBox HSE 8 MHz, SSD1309 OLED 128×64 monochrome. Profile `saolalink-devebox`, PCB X7 / SAOLALINK_V1, Debug + LTO, GNU ARM 14.2.1, CMake Generic/arm-none-eabi. Bộ này đã PASS configure/compile/link qua nút Build firmware của SaolaLink Studio ở lượt trước. Tác vụ backup không build lại vì không thay đổi source firmware và cần giữ đúng BIN đã được người dùng kiểm tra. [Tùy chọn tái tạo](BUILD_OPTIONS.json), [hướng dẫn build/test](BUILD.md).

**Tính năng có trong bản BIN**

| Nhóm | Hành vi |
|---|---|
| HOME | Chỉ HOME TYVOR V1, giữ layout hiện tại, không đồng hồ RTC hoặc logo TYVOR trên HOME |
| Telemetry/MODE/ARM | Dữ liệu thật, freshness; bỏ một dấu * cuối bản hiển thị MODE, không thay sensor FM; profile Betaflight 4.5.5 lưu theo model, verified/sensor đúng mới giải mã ARM; không dùng switch làm bằng chứng FC ARM |
| Flight Timer | AUTO từ nguồn FC được xác minh; SWITCH có nguồn cấu hình theo model; độc lập Timer1, monotonic; giữ cấu hình đã lưu |
| RQly | Uplink TX→RX, 0–100% thành 0–5 cột, thiếu/stale thành chưa xác định; không dùng TQly hoặc TX power |
| Channel Monitor | HOME giữ ENTER → Channel Monitor; CH1–32, ENTER chuyển output/mixer, EXIT về nơi gọi; không khôi phục HOME legacy |
| DRONE | Điện áp telemetry; vạch chỉ từ phần trăm FC hợp lệ; thiếu dữ liệu không giả mức pin |
| SATS | CRSF 0x02 instance 5, RAW precision 0; số 0 hợp lệ, thiếu/stale → -- |
| ALT | CRSF 0x09 instance 0, METERS; tương đối theo điểm start/calibration FC, không tự đặt mốc cất cánh; thiếu/sai/stale → -- |
| Power/branding | Starting power ring một lần ~1,2 s → splash cú mèo gốc 1,5 s → HOME; shutdown power ring giảm một lần theo thời gian shutdown hiện có; giữ quyền ưu tiên input/cảnh báo |
| UI khác | Trainer hidden; Settings/Telemetry/Discover hoạt động; simulator Power cycle và joystick Mode 1–4 giữ nguyên |

Giới hạn ALT: source chuẩn Betaflight 4.5.5 không phát frame 0x09; GAlt 0x02 đổi mốc theo ARM/nguồn cảm biến và có thể giữ số cũ khi mất fix. Bản stable **không fallback GAlt/TX**. Trên FC BETAFPVF411 chưa có nguồn altitude đã xác minh thì ALT -- là có chủ đích. Không giả giá trị GPS/altitude/ARM.

**Xác minh và phạm vi**

- **CONFIRMED BY USER:** bộ firmware hiện tại đã được nạp và hoạt động tốt trên TYVOR thật theo yêu cầu backup ngày 29/10/2026. Flight Timer SWITCH đã được người dùng xác nhận hoạt động trước đó. Không thực hiện đọc ngược flash để chứng minh byte trên thiết bị.
- **PASS:** chạy lại 53/53 regression trong lượt backup, không skip; kiểm tra ELF có menu FC ARM/Flight Timer/Channel Monitor, BIN có model keys và nhãn HOME; SHA256, application split, vector, giới hạn flash, bootloader 32 KiB.
- **PASS trước đó với cùng source/BIN:** WSLg framebuffer 128×64, telemetry fixtures, navigation/Settings/Discover/Channel Monitor; Studio ARM GNU 14.2.1 compile/link. Không chạy lại WSLg trong tác vụ backup.
- **NOT VERIFIED riêng trên drone thật:** altitude hợp lệ, SATS thực tế, AUTO timer và chuyển trạng thái FC ARMED nếu chưa có phép thử được ghi nhận. Xác nhận hoạt động chung không thay thế kiểm thử từng trường hợp hay thử bay.

Kết quả tổng hợp lưu trong [TEST_RESULTS.json](TEST_RESULTS.json). Log/cache/build tạm nằm ngoài gói release, trong thư mục build đã ignore. Ảnh [HOME simulator](home-simulator.png) dùng telemetry fixture kiểm thử, không phải ảnh tay thật.

**Artifact nguyên bản**

| File | Byte | Địa chỉ/mô tả |
|---|---:|---|
| [firmware.bin](firmware.bin) | 512504 | 0x08000000; có vùng bootloader đầu 32 KiB |
| [application.bin](application.bin) | 479736 | 0x08008000; khớp firmware.bin[32768:] |

Flash tổng 524288 byte; image kết thúc 0x0807D1F8, giới hạn 0x08080000; còn **11784 byte**. Giữ nguyên flash layout.

SHA256 firmware: `a5c828f886c1fbeaf8b2b9fbc69d301beecee593cfae43434d7235a9f6b989fd`.

SHA256 application: `6b44afc3036da11aed99ad672454bdc19f138f904b3f9be864432eb1fde7df55`.

SHA256 đủ vùng bootloader 32768 byte: `6a38127fe00c226b131c56c3bd2de563530cfb926ee75f371c3f0e58a1465f8b`. Bootloader nhị phân 22580 byte nằm đầu vùng đó: `fc837f947dcfe43ea796d68c076e9119715827a3e2a2a5167e140c3a3699f508`. Cả hai giữ nguyên so với bản trước; phần padding được tính trong hash 32 KiB.

Xác minh chỉ đọc, không flash:

```sh
python3 releases/tyvor-v1-stable-20261029/verify_backup.py
```

Trên Windows có thể dùng `py` hoặc Python venv Studio thay `python3`. [SHA256SUMS](SHA256SUMS) là hash BIN nguyên byte; [RELEASE_FILES.sha256](RELEASE_FILES.sha256) kiểm tra toàn gói trừ chính file checksum. Attribute cục bộ giữ text LF và BIN/PNG binary để tránh Git đổi dữ liệu.

[Source state](SOURCE_STATE.json) ghi base commit, hash source/test/assets và commit dependency. Hash `bytes_sha256` nhận diện working tree hiện tại; `lf_sha256` dùng so sánh source text sau checkout khác CRLF/LF. Hai manifest BIN gốc được giữ nguyên, không giả rằng base commit đã chứa các file WIP. Build sau commit/tag có thể đổi version stamp và debug path, nên chưa cam kết bit-for-bit; bản stable này được bảo toàn bằng checksum.

Không flash, commit, push, merge, deploy; không reset hoặc xóa WIP trong tác vụ sao lưu. Các lệnh Git bên dưới chỉ là hướng dẫn để người dùng tự kiểm tra và thực hiện.
