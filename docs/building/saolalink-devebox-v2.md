# DevEBox 8 MHz V2 — SSD1309 SPI

This target remains separate from DevEBox Base, sharing its SPI display driver. It uses an
STM32F407VET6, 8 MHz HSE, 512 KiB flash and 32 KiB USB bootloader region.

Use Git branch `SAOLALINKV2` for this target. `SAOLALINKV1` remains the
V1/Base checkpoint; selecting a Studio profile does not switch Git branches.

| Configuration | Value |
| --- | --- |
| PCB / PCBREV | `X7` / `DEVEBOX_V2` |
| Hardware JSON / flavour | `devebox8v2` |
| Target source | `radio/src/targets/taranis/devebox_v2/` |
| Studio profile | `saolalink-devebox-v2` |
| Display | SSD1309 128×64, SPI3 2.625 MHz, DMA |

Display wiring matches Base: SCK/CLK PC10, MOSI/DIN/SDA PC12, RESET PD12,
DC/A0 PC11, CS PA15, common GND, and the same module's 5 V supply. The MCU
uses 3.3 V logic. Labels SCL/SDA on this SPI module mean SPI clock/data.
PB8/PB9 are no longer display pins; PB6/PB7 remain the internal RF UART.

From this repository, using the existing Arm toolchain setup:

```sh
cmake -S . -B build/devebox-v2 \
  -DPCB=X7 -DPCBREV=DEVEBOX_V2 \
  -DSAOLALINK_HSE_HZ=8000000 -DBLUETOOTH=OFF \
  -DCMAKE_BUILD_TYPE=Debug -DDEFAULT_MODE=2 -DTRANSLATIONS=EN \
  -DUSE_FW_LTO=ON -DBOOTLOADER=ON \
  -DFIRMWARE_STRIP_BOOTLOADER=OFF -DFIRMWARE_FORMAT_UF2=OFF
cmake --build build/devebox-v2 --target firmware hardware_defs --parallel 4
```

Studio keeps V2 outputs separate from Base and generates application-only
images at `0x08008000`. Both targets share the corrected USB loader: install
it once through ROM DFU, then use Upload / wait for USB with BOOT0=0.
Do not send a full bootloader-inclusive image to the application address.

V2 preserves the second prototype's SD diagnostics. The temporary slow-SD
settings were removed on 2026-11-05: SPI2 now uses the normal EdgeTX clock
limits (about 328 kHz initialization / 21 MHz transfers at APB1=42 MHz)
and normal GPIO speed. CDC starts before
SD settings load. PA1 toggles every 100 ms during startup and every 500 ms
in the normal main task. `devboard` reports startup, SD and the SPI LCD pins.
The V2 CDC fix preserves configured callbacks across USB class reset and
releases them on serial-driver deinit.

On 2026-11-05 the user replaced the earlier I²C module with the same SPI
module as Base. The target now selects the shared `lcd_driver_spi.cpp`,
SPI3/DMA, prescaler /16 (2.625 MHz), and A1/C8 orientation exactly as Base.
The earlier V2 I²C driver and its tests are removed from the active source;
its source/binaries are backed up in the parent workspace. Existing I²C
binaries must be replaced with a new SPI application build. The user confirmed
the replacement SPI display works on 2026-11-05.

V2 shows only the four-dot sequence while reading SD settings, without a
loading message. One dot is added every 200 ms; all four appear at 800 ms and
the sequence completes at one second. Settings reads start immediately. The
app waits only for any remaining animation time after loading, then enters
the interface. Slow reads keep all four dots visible until data is ready,
without restarting the count or adding another second after loading.
The startup task refreshes between completed SD transactions, limited to one
redraw per 40 ms. Other tasks cannot draw this startup UI; alerts and fatal
SD errors stop it immediately before showing their message. `devboard`
reports progress frames and the actual display duration in milliseconds.
The existing power latch and initial-hold shutdown filter are unchanged.
The updated V2 loader offers a 500 ms USB window before the app (Base stays at two seconds).
The V2 early bootloader hook also starts LSE without waiting, overlapping
RTC crystal stabilization with the USB window. RTC initialization may still
need additional time after the shortened window. It never
resets the backup domain or changes the RTC clock source. Installing the new
bootloader through ROM DFU is required for that optimization. The app retains
normal RTC initialization and reports RTC/display/SD/settings timing through
`devboard`; application timestamps exclude the bootloader's time.

The V2 USB window is shortened from 2000 to 500 ms. Install the new loader
through ROM DFU once; an app-only upload cannot change the installed window.
Arm Studio Upload before reconnect/reset. Studio polls every 20 ms between
USB scans for V2. A valid DfuSe SET_ADDRESS claims the session and prevents
timeout during flashing, including a request on the timeout tick. Scans do
not claim a session. RTN/invalid-image recovery remains indefinite. On 2026-11-05 the loader was installed via ROM DFU on serial 305739623433;
full flash readback verified the loader and unchanged app region. Studio's
updated discovery captured the 500 ms window on the tested machine, read the
app vectors, held the session beyond one second, and uploaded the application
successfully. Manifestation returned to running firmware/CDC with SD mounted.
The user also confirmed faster startup after reset. This is one actual
capture/upload test; other host/driver combinations were not measured.


## AUX UART host connection

V2 uses the existing USART3 AUX1 port: PB10 TX, PB11 RX, AF7, DMA1 Stream1 RX.
PB12 stays SD chip select. Connect host RX to PB10, host TX to PB11, and common
GND, with 3.3 V UART logic. The existing Lua serial mode provides 115200 8N1,
non-inverted bidirectional communication. New V2 radio defaults select this
mode when Lua is compiled; SD-loaded modes remain authoritative.
For existing settings, USB CLI `auxuart on` selects/initializes AUX1 Lua serial
and marks radio settings dirty for normal storage. `auxuart [status]` is
read-only. `devboard` reports AUX mode, actual baud, active driver and USART3
CR1. USB CLI remains on VCP; navigation keys/encoder, RF and SD are unchanged.
No UART-to-navigation command parser or input injection is added.

The AUX application was uploaded to serial 305739623433 on 2026-11-05 and
`auxuart on` enabled the saved port. After normal storage and reset, mode 5
remained active with USART3 CR1=0x200C (UE, TE, RE set). Driver baud readback
was 115384 for nominal 115200. USB CLI returned running status and SD remained
mounted at 21 MHz with valid CID/CRC. 22 firmware regressions passed and Base
binary hash remained unchanged. This verifies UART setup/persistence, without
an external Orange Pi/Android/loopback data test.
